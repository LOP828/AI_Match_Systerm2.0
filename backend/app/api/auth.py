import threading
from collections import defaultdict, deque
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import ActorContext, create_access_token, get_actor_context, require_privileged_role
from app.audit import audit_log
from app.config import Settings, get_settings
from app.db import get_db
from app.models import UserProfile
from app.schemas.auth import (
    CredentialResponse,
    CredentialUpsertRequest,
    LoginRequest,
    MeResponse,
    TokenIssueRequest,
    TokenResponse,
)
from app.services.auth_service import authenticate_with_password, upsert_password_credential

router = APIRouter()

MAX_LOGIN_ATTEMPTS = 5        # per IP+user_id pair
MAX_IP_LOGIN_ATTEMPTS = 30   # per IP across all user_ids (prevents cross-user enumeration)
LOGIN_WINDOW_SECONDS = 300

_rate_lock = threading.Lock()
_failed_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def _prune_attempts(attempts: deque[float], now: float) -> None:
    while attempts and now - attempts[0] > LOGIN_WINDOW_SECONDS:
        attempts.popleft()


def _ensure_login_not_rate_limited(request: Request, user_id: int) -> tuple[str, str]:
    client_host = request.client.host if request.client else "unknown"
    pair_key = f"{client_host}:{user_id}"
    ip_key = f"ip:{client_host}"
    now = monotonic()

    with _rate_lock:
        pair_attempts = _failed_login_attempts[pair_key]
        ip_attempts = _failed_login_attempts[ip_key]
        _prune_attempts(pair_attempts, now)
        _prune_attempts(ip_attempts, now)

        if len(pair_attempts) >= MAX_LOGIN_ATTEMPTS or len(ip_attempts) >= MAX_IP_LOGIN_ATTEMPTS:
            audit_log("user.login", "rate_limited", request=request, targetUserId=user_id)
            raise HTTPException(status_code=429, detail="Too many login attempts, please retry later")

    return pair_key, ip_key


def _record_login_failure(pair_key: str, ip_key: str) -> None:
    now = monotonic()
    with _rate_lock:
        for key in (pair_key, ip_key):
            attempts = _failed_login_attempts[key]
            _prune_attempts(attempts, now)
            attempts.append(now)


def _clear_login_failures(pair_key: str, ip_key: str) -> None:
    # Only clear the per-user pair bucket on success; the per-IP bucket intentionally
    # keeps its history so that cross-user enumeration attempts are not reset by one
    # lucky correct login.
    with _rate_lock:
        _failed_login_attempts.pop(pair_key, None)


@router.post('/login', response_model=TokenResponse)
def login_with_password(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    pair_key, ip_key = _ensure_login_not_rate_limited(request, body.userId)
    authenticated_user = authenticate_with_password(db, body.userId, body.password)
    if authenticated_user is None:
        _record_login_failure(pair_key, ip_key)
        audit_log("user.login", "failure", request=request, targetUserId=body.userId)
        raise HTTPException(status_code=401, detail='Invalid credentials')

    _clear_login_failures(pair_key, ip_key)

    access_token = create_access_token(
        authenticated_user.user_id,
        authenticated_user.role,
        settings,
        expires_minutes=settings.jwt_expire_minutes,
    )
    audit_log(
        "user.login",
        "success",
        request=request,
        targetUserId=authenticated_user.user_id,
        issuedRole=authenticated_user.role,
    )
    return TokenResponse(accessToken=access_token, expiresInSeconds=settings.jwt_expire_minutes * 60)


@router.post('/credential', response_model=CredentialResponse)
def upsert_credential(
    body: CredentialUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    is_privileged_actor = actor.role in settings.privileged_role_set

    if body.userId != actor.user_id:
        require_privileged_role(actor, settings)
    elif settings.auth_required and not is_privileged_actor and body.role != actor.role:
        audit_log(
            "auth.credential_upsert",
            "failure",
            actor=actor,
            request=request,
            targetUserId=body.userId,
            targetRole=body.role,
            reason="self_role_change_forbidden",
        )
        raise HTTPException(status_code=403, detail="Cannot change your own role")

    try:
        credential = upsert_password_credential(db, body.userId, body.password, body.role)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if 'does not exist' in message else 422
        audit_log("auth.credential_upsert", "failure", actor=actor, request=request, targetUserId=body.userId, targetRole=body.role, reason=message)
        raise HTTPException(status_code=status_code, detail=message) from exc

    audit_log("auth.credential_upsert", "success", actor=actor, request=request, targetUserId=body.userId, targetRole=credential.role)
    return CredentialResponse(userId=credential.user_id, role=credential.role)


@router.post('/token', response_model=TokenResponse)
def issue_token(
    body: TokenIssueRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    role = body.role.strip().lower() or 'user'

    is_privileged_actor = actor.role in settings.privileged_role_set
    if not is_privileged_actor:
        if actor.user_id is None:
            audit_log("auth.token_issue", "failure", actor=actor, request=request, targetUserId=body.userId, requestedRole=role, reason="missing_authentication")
            raise HTTPException(status_code=401, detail='Authentication required to issue token')
        if actor.user_id != body.userId:
            audit_log("auth.token_issue", "failure", actor=actor, request=request, targetUserId=body.userId, requestedRole=role, reason="cross_user_token_forbidden")
            raise HTTPException(status_code=403, detail='Cannot issue token for another user')
        if role != actor.role:
            audit_log("auth.token_issue", "failure", actor=actor, request=request, targetUserId=body.userId, requestedRole=role, reason="role_escalation_forbidden")
            raise HTTPException(status_code=403, detail='Cannot escalate role')

    user_exists = db.query(UserProfile.user_id).filter(UserProfile.user_id == body.userId).first()
    if not user_exists:
        audit_log("auth.token_issue", "failure", actor=actor, request=request, targetUserId=body.userId, requestedRole=role, reason="user_not_found")
        raise HTTPException(status_code=404, detail='User not found')

    ttl = body.ttlMinutes if body.ttlMinutes is not None else settings.jwt_expire_minutes
    access_token = create_access_token(body.userId, role, settings, expires_minutes=ttl)
    audit_log("auth.token_issue", "success", actor=actor, request=request, targetUserId=body.userId, requestedRole=role, ttlMinutes=ttl)
    return TokenResponse(accessToken=access_token, expiresInSeconds=ttl * 60)


@router.get('/me', response_model=MeResponse)
def get_me(
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    return MeResponse(
        userId=actor.user_id,
        role=actor.role,
        source=actor.source,
        privileged=actor.role in settings.privileged_role_set,
    )
