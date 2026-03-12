from collections import Counter
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import InteractionEvent, InteractionMemo, UserProfile
from app.time_utils import to_api_datetime


def _ensure_user_exists(db: Session, user_id: int) -> None:
    exists = db.query(UserProfile.user_id).filter(UserProfile.user_id == user_id).first()
    if not exists:
        raise ValueError(f"User {user_id} does not exist")


def record_meeting(
    db: Session,
    user_a_id: int,
    user_b_id: int,
    willingness_a: str,
    willingness_b: str,
    issue_tags_json: list[str] | None,
    memo_text: str,
    created_by: int | None = None,
    conversation_smoothness: int | None = None,
    appearance_acceptance: int | None = None,
    values_alignment: int | None = None,
    reject_reason_primary: str | None = None,
    reject_reason_secondary: str | None = None,
) -> dict[str, Any]:
    _ensure_user_exists(db, user_a_id)
    _ensure_user_exists(db, user_b_id)
    if created_by is not None:
        _ensure_user_exists(db, created_by)

    event = InteractionEvent(
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        event_type="meet",
        willingness_a=willingness_a,
        willingness_b=willingness_b,
        issue_tags_json=issue_tags_json,
        conversation_smoothness=conversation_smoothness,
        appearance_acceptance=appearance_acceptance,
        values_alignment=values_alignment,
        reject_reason_primary=reject_reason_primary,
        reject_reason_secondary=reject_reason_secondary,
        created_by=created_by,
    )
    db.add(event)
    db.flush()

    if memo_text:
        memo = InteractionMemo(
            related_event_id=event.event_id,
            author_id=created_by or user_a_id,
            raw_text=memo_text,
        )
        db.add(memo)

    db.commit()
    db.refresh(event)
    return {"success": True, "eventId": event.event_id}


def _event_to_history_dict(event: InteractionEvent, memo_text: str | None) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "user_a_id": event.user_a_id,
        "user_b_id": event.user_b_id,
        "willingness_a": event.willingness_a,
        "willingness_b": event.willingness_b,
        "conversation_smoothness": event.conversation_smoothness,
        "appearance_acceptance": event.appearance_acceptance,
        "values_alignment": event.values_alignment,
        "reject_reason_primary": event.reject_reason_primary,
        "reject_reason_secondary": event.reject_reason_secondary,
        "issue_tags_json": event.issue_tags_json,
        "memo_text": memo_text,
        "event_time": to_api_datetime(event.event_time),
        "created_at": to_api_datetime(event.created_at),
    }


def get_interaction_history(
    db: Session,
    user_a_id: int,
    user_b_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    events = (
        db.query(InteractionEvent)
        .filter(
            ((InteractionEvent.user_a_id == user_a_id) & (InteractionEvent.user_b_id == user_b_id))
            | ((InteractionEvent.user_a_id == user_b_id) & (InteractionEvent.user_b_id == user_a_id))
        )
        .order_by(InteractionEvent.event_time.desc(), InteractionEvent.event_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    event_ids = [event.event_id for event in events]
    memos_by_event: dict[int, InteractionMemo] = {}
    if event_ids:
        memos = (
            db.query(InteractionMemo)
            .filter(InteractionMemo.related_event_id.in_(event_ids))
            .order_by(InteractionMemo.memo_id.desc())
            .all()
        )
        for memo in memos:
            memos_by_event.setdefault(memo.related_event_id, memo)

    return [
        _event_to_history_dict(
            event,
            memos_by_event.get(event.event_id).raw_text if memos_by_event.get(event.event_id) else None,
        )
        for event in events
    ]


def get_user_feedback_history(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Get all feedback events involving a single user (as A or B)."""
    events = (
        db.query(InteractionEvent)
        .filter(
            InteractionEvent.event_type == "meet",
            or_(
                InteractionEvent.user_a_id == user_id,
                InteractionEvent.user_b_id == user_id,
            ),
        )
        .order_by(InteractionEvent.event_time.desc(), InteractionEvent.event_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    event_ids = [e.event_id for e in events]
    memos_by_event: dict[int, InteractionMemo] = {}
    if event_ids:
        memos = (
            db.query(InteractionMemo)
            .filter(InteractionMemo.related_event_id.in_(event_ids))
            .order_by(InteractionMemo.memo_id.desc())
            .all()
        )
        for memo in memos:
            memos_by_event.setdefault(memo.related_event_id, memo)

    return [
        _event_to_history_dict(
            event,
            memos_by_event.get(event.event_id).raw_text if memos_by_event.get(event.event_id) else None,
        )
        for event in events
    ]


def get_feedback_signals(db: Session, user_id: int) -> dict[str, Any]:
    """Aggregate structured feedback signals for a user, for recommendation correction."""
    events = (
        db.query(InteractionEvent)
        .filter(
            InteractionEvent.event_type == "meet",
            or_(
                InteractionEvent.user_a_id == user_id,
                InteractionEvent.user_b_id == user_id,
            ),
        )
        .limit(200)
        .all()
    )

    total = len(events)
    if total == 0:
        return {
            "userId": user_id,
            "totalMeetings": 0,
            "avgConversationSmoothness": None,
            "avgAppearanceAcceptance": None,
            "avgValuesAlignment": None,
            "topRejectReasons": [],
            "continueRate": None,
        }

    smoothness_vals = [e.conversation_smoothness for e in events if e.conversation_smoothness is not None]
    appearance_vals = [e.appearance_acceptance for e in events if e.appearance_acceptance is not None]
    alignment_vals = [e.values_alignment for e in events if e.values_alignment is not None]

    reject_reasons: list[str] = []
    continue_count = 0
    for e in events:
        if e.reject_reason_primary:
            reject_reasons.append(e.reject_reason_primary)
        if e.reject_reason_secondary:
            reject_reasons.append(e.reject_reason_secondary)

        # Count "continue" — check the side that corresponds to this user
        if e.user_a_id == user_id and e.willingness_a == "yes":
            continue_count += 1
        elif e.user_b_id == user_id and e.willingness_b == "yes":
            continue_count += 1

    top_reasons = [reason for reason, _ in Counter(reject_reasons).most_common(3)]

    return {
        "userId": user_id,
        "totalMeetings": total,
        "avgConversationSmoothness": round(sum(smoothness_vals) / len(smoothness_vals), 2) if smoothness_vals else None,
        "avgAppearanceAcceptance": round(sum(appearance_vals) / len(appearance_vals), 2) if appearance_vals else None,
        "avgValuesAlignment": round(sum(alignment_vals) / len(alignment_vals), 2) if alignment_vals else None,
        "topRejectReasons": top_reasons,
        "continueRate": round(continue_count / total, 2) if total > 0 else None,
    }
