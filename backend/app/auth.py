from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import InvalidTokenError

from app.choices import ROLE_VALUES
from app.config import Settings, get_settings


@dataclass(frozen=True)
class ActorContext:
    user_id: int | None
    role: str
    source: str = "none"


def _normalize_role(role: str | None) -> str:
    normalized = (role or "user").strip().lower()
    if normalized not in ROLE_VALUES:
        raise HTTPException(status_code=401, detail="Invalid actor role")
    return normalized


def create_access_token(
    user_id: int,
    role: str,
    settings: Settings,
    expires_minutes: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    ttl_minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    expires_at = now + timedelta(minutes=max(1, int(ttl_minutes)))
    payload = {
        "sub": str(user_id),
        "role": _normalize_role(role),
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> ActorContext:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_seconds,
            options={"require": ["sub", "role", "iss", "exp", "iat", "nbf"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from exc

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token subject") from exc

    role = _normalize_role(str(payload.get("role") or "user"))
    return ActorContext(user_id=user_id, role=role, source="jwt")


def get_actor_context(
    authorization: str | None = Header(None, alias="Authorization"),
    x_user_id: int | None = Header(None, alias="X-User-Id"),
    x_role: str | None = Header(None, alias="X-Role"),
    settings: Settings = Depends(get_settings),
) -> ActorContext:
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            if not token:
                raise HTTPException(status_code=401, detail="Empty bearer token")
            return decode_access_token(token, settings)
        raise HTTPException(status_code=401, detail="Unsupported authorization scheme")

    if settings.legacy_headers_enabled and x_user_id is not None:
        role = _normalize_role(x_role or "user")
        return ActorContext(user_id=x_user_id, role=role, source="legacy_header")

    if x_user_id is not None and not settings.legacy_headers_enabled:
        raise HTTPException(status_code=401, detail="Legacy actor headers are disabled")

    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")

    return ActorContext(user_id=None, role="anonymous", source="none")


def require_resource_access(
    actor: ActorContext,
    target_user_id: int,
    settings: Settings,
) -> None:
    if not settings.auth_required:
        return
    if actor.user_id == target_user_id:
        return
    if actor.role in settings.privileged_role_set:
        return
    raise HTTPException(status_code=403, detail="Forbidden")


def require_privileged_role(
    actor: ActorContext,
    settings: Settings,
) -> None:
    if not settings.auth_required:
        return
    if actor.role in settings.privileged_role_set:
        return
    raise HTTPException(status_code=403, detail="Privileged role required")
