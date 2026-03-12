"""Tests for AI extraction approve-writeback flow."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import Settings
from app.models import (
    AiExtraction,
    InteractionEvent,
    InteractionMemo,
    UserConstraint,
    UserObservationTag,
    UserProfile,
    VerifyTask,
)
from app.services.auth_service import upsert_password_credential


def _bearer_headers(user_id: int, role: str, settings: Settings) -> dict[str, str]:
    token = create_access_token(user_id, role, settings)
    return {"Authorization": f"Bearer {token}"}


def _seed(db: Session) -> tuple[int, int]:
    """Create users, event, memo, and return (memo_id, extraction_obs_id)."""
    db.add_all(
        [
            UserProfile(user_id=1, active_status="active", open_to_match=1),
            UserProfile(user_id=2, active_status="active", open_to_match=1),
            UserProfile(user_id=10, active_status="active", open_to_match=1),
        ]
    )
    db.flush()

    event = InteractionEvent(
        user_a_id=1,
        user_b_id=2,
        event_type="meet",
    )
    db.add(event)
    db.flush()

    memo = InteractionMemo(
        related_event_id=event.event_id,
        author_id=10,
        raw_text="test memo",
    )
    db.add(memo)
    db.flush()

    return memo.memo_id, event.event_id


def test_approve_observation_creates_tag(client, db_session: Session, test_settings: Settings):
    """Approving an observation extraction creates a UserObservationTag."""
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="personality_cheerful",
        extracted_value="cheerful",
        confidence=Decimal("85"),
        extraction_type="observation",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()
    ext_id = ext.extraction_id

    resp = client.post(f"/api/ai-extraction/{ext_id}/approve?reviewedBy=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["appliedAction"] == "create_observation_tag"
    assert body["createdObservationTagId"] is not None

    tag = db_session.query(UserObservationTag).filter(
        UserObservationTag.tag_id == body["createdObservationTagId"]
    ).first()
    assert tag is not None
    assert tag.user_id == 2  # user_b from event
    assert tag.tag_code == "personality_cheerful"
    assert tag.observer_type == "ai"


def test_approve_high_risk_creates_constraint(client, db_session: Session, test_settings: Settings):
    """Approving a high-confidence risk extraction creates a UserConstraint."""
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="smoking_status",
        extracted_value="yes",
        confidence=Decimal("80"),
        extraction_type="risk",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.post(f"/api/ai-extraction/{ext.extraction_id}/approve?reviewedBy=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["appliedAction"] == "create_constraint"
    assert body["createdConstraintId"] is not None

    constraint = db_session.query(UserConstraint).filter(
        UserConstraint.constraint_id == body["createdConstraintId"]
    ).first()
    assert constraint is not None
    assert constraint.user_id == 2
    assert constraint.tag_code == "smoking_status"
    assert constraint.tag_type == "block"
    assert constraint.applies_to_field == "smoking_status"
    candidate = db_session.query(UserProfile).filter(UserProfile.user_id == 2).one()
    assert candidate.smoking_status == "yes"


def test_approve_low_risk_creates_verify_task(client, db_session: Session, test_settings: Settings):
    """Approving a low-confidence risk extraction creates a VerifyTask."""
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="drinking_status",
        extracted_value="heavy",
        confidence=Decimal("55"),
        extraction_type="risk",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.post(f"/api/ai-extraction/{ext.extraction_id}/approve?reviewedBy=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["appliedAction"] == "create_verify_task"
    assert body["createdVerifyTaskId"] is not None

    task = db_session.query(VerifyTask).filter(
        VerifyTask.task_id == body["createdVerifyTaskId"]
    ).first()
    assert task is not None
    assert task.requester_user_id == 1  # user_a
    assert task.candidate_user_id == 2  # user_b
    assert task.task_status == "pending"


def test_high_confidence_invalid_structured_value_falls_back_to_verify_task(client, db_session: Session, test_settings: Settings):
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="drinking_status",
        extracted_value="heavy",
        confidence=Decimal("90"),
        extraction_type="risk",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.post(f"/api/ai-extraction/{ext.extraction_id}/approve?reviewedBy=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["appliedAction"] == "create_verify_task"
    assert body["createdVerifyTaskId"] is not None
    assert db_session.query(UserConstraint).filter(UserConstraint.source_ref_id == ext.extraction_id).count() == 0


def test_approve_unmapped_risk_skips_writeback(client, db_session: Session, test_settings: Settings):
    """High-confidence risks without a structured target field should not create broken writeback rows."""
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="financial_risk",
        extracted_value="high_debt",
        confidence=Decimal("90"),
        extraction_type="risk",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.post(f"/api/ai-extraction/{ext.extraction_id}/approve?reviewedBy=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["appliedAction"] == "none"
    assert db_session.query(UserConstraint).filter(UserConstraint.source_ref_id == ext.extraction_id).count() == 0
    assert db_session.query(VerifyTask).filter(VerifyTask.trigger_reason.like(f"AI extraction #{ext.extraction_id}%")).count() == 0


def test_reject_does_not_writeback(client, db_session: Session, test_settings: Settings):
    """Rejecting an extraction does NOT create any business entities."""
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="personality_kind",
        extracted_value="kind",
        confidence=Decimal("90"),
        extraction_type="observation",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.post(f"/api/ai-extraction/{ext.extraction_id}/reject?reviewedBy=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    tags = db_session.query(UserObservationTag).filter(
        UserObservationTag.source_ref_id == ext.extraction_id
    ).all()
    assert len(tags) == 0


def test_get_extractions_includes_suggested_action(client, db_session: Session, test_settings: Settings):
    """GET extraction list includes extraction_type and suggested_action."""
    memo_id, _ = _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    ext = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label="trait_honest",
        extracted_value="honest",
        confidence=Decimal("88"),
        extraction_type="observation",
        extraction_status="suggested",
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.get(f"/api/ai-extraction/?entityType=memo&entityId={memo_id}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    item = items[0]
    assert item["extraction_type"] == "observation"
    assert item["suggested_action"] == "create_observation_tag"
