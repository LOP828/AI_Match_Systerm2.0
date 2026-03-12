from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor_context, require_privileged_role
from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.feedback import FeedbackSignals, InteractionHistoryItem, RecordMeetingRequest
from app.services.feedback_service import (
    get_feedback_signals,
    get_interaction_history,
    get_user_feedback_history,
    record_meeting,
)

router = APIRouter()


def _ensure_actor_in_pair_or_privileged(actor: ActorContext, settings: Settings, user_a_id: int, user_b_id: int) -> None:
    if not settings.auth_required:
        return
    if actor.role in settings.privileged_role_set:
        return
    if actor.user_id in {user_a_id, user_b_id}:
        return
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/meeting")
def post_record_meeting(
    body: RecordMeetingRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_privileged_role(actor, settings)

    try:
        return record_meeting(
            db,
            user_a_id=body.userAId,
            user_b_id=body.userBId,
            willingness_a=body.willingnessA,
            willingness_b=body.willingnessB,
            issue_tags_json=body.issueTagsJson,
            memo_text=body.memoText,
            created_by=actor.user_id if settings.auth_required else None,
            conversation_smoothness=body.conversationSmoothness,
            appearance_acceptance=body.appearanceAcceptance,
            values_alignment=body.valuesAlignment,
            reject_reason_primary=body.rejectReasonPrimary,
            reject_reason_secondary=body.rejectReasonSecondary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/history", response_model=list[InteractionHistoryItem])
def get_history(
    userAId: int = Query(..., alias="userAId"),
    userBId: int = Query(..., alias="userBId"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    _ensure_actor_in_pair_or_privileged(actor, settings, userAId, userBId)
    return get_interaction_history(db, userAId, userBId, limit=limit, offset=offset)


@router.get("/history/{user_id}", response_model=list[InteractionHistoryItem])
def get_user_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    _ensure_actor_in_pair_or_privileged(actor, settings, user_id, user_id)
    return get_user_feedback_history(db, user_id, limit=limit, offset=offset)


@router.get("/signals/{user_id}", response_model=FeedbackSignals)
def get_signals(
    user_id: int,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    _ensure_actor_in_pair_or_privileged(actor, settings, user_id, user_id)
    return get_feedback_signals(db, user_id)
