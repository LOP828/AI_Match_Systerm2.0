from typing import Any

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
        {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "user_a_id": event.user_a_id,
            "user_b_id": event.user_b_id,
            "willingness_a": event.willingness_a,
            "willingness_b": event.willingness_b,
            "issue_tags_json": event.issue_tags_json,
            "memo_text": memos_by_event.get(event.event_id).raw_text if memos_by_event.get(event.event_id) else None,
            "event_time": to_api_datetime(event.event_time),
            "created_at": to_api_datetime(event.created_at),
        }
        for event in events
    ]
