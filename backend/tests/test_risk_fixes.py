from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.ai_extraction import EXTRACTION_TRIGGER_LABEL, _reserve_extraction_job, _suggest_action
from app.auth import get_actor_context
from app.config import Settings
from app.models import AiExtraction, InteractionEvent, InteractionMemo, UserConstraint, UserPreference, UserProfile
from app.profile_fields import normalize_profile_field_value
from app.schemas.feedback import RecordMeetingRequest
from app.schemas.profile import ConstraintCreate
from app.services.llm_extraction_service import extract_from_memo
from app.services.rule_engine import collect_unknown_constraints, filter_by_hard_rules
from app.time_utils import utc_now


def test_constraint_schema_rejects_unsupported_field_and_penalty_tag():
    with pytest.raises(ValidationError):
        ConstraintCreate(tag_code="bad", tag_type="verify", applies_to_field="favorite_color")

    with pytest.raises(ValidationError):
        ConstraintCreate(tag_code="bad", tag_type="penalty", applies_to_field="smoking_status")


def test_feedback_schema_rejects_same_user_pair():
    with pytest.raises(ValidationError):
        RecordMeetingRequest(
            userAId=1,
            userBId=1,
            willingnessA="yes",
            willingnessB="yes",
            memoText="invalid",
        )


def test_legacy_headers_are_ignored_outside_test_environment():
    settings = Settings(
        environment="development",
        auth_required=True,
        allow_legacy_headers=True,
        jwt_secret_key="test-secret-key-with-32-bytes-minimum",
    )

    with pytest.raises(HTTPException) as exc_info:
        get_actor_context(authorization=None, x_user_id=1, x_role="user", settings=settings)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Legacy actor headers are disabled"


def test_legacy_headers_still_work_in_test_environment():
    settings = Settings(
        environment="test",
        auth_required=True,
        allow_legacy_headers=True,
        jwt_secret_key="test-secret-key-with-32-bytes-minimum",
    )

    actor = get_actor_context(authorization=None, x_user_id=1, x_role="admin", settings=settings)
    assert actor.user_id == 1
    assert actor.role == "admin"
    assert actor.source == "legacy_header"


def test_profile_field_normalization_rejects_invalid_enum_and_range():
    assert normalize_profile_field_value("smoking_status", " YES ") == "yes"

    with pytest.raises(ValueError):
        normalize_profile_field_value("smoking_status", "heavy")

    with pytest.raises(ValueError):
        normalize_profile_field_value("age", 200)


def test_collect_unknown_constraints_ignores_legacy_invalid_field(db_session: Session):
    candidate = UserProfile(user_id=2, smoking_status="unknown")
    db_session.add(candidate)
    db_session.flush()

    valid = UserConstraint(
        user_id=1,
        tag_code="need_smoking_status",
        tag_type="verify",
        applies_to_field="smoking_status",
        status="active",
    )
    invalid = UserConstraint(
        user_id=1,
        tag_code="legacy_bad",
        tag_type="verify",
        applies_to_field="favorite_color",
        status="active",
    )

    unknown = collect_unknown_constraints(candidate, [valid, invalid])
    assert [constraint.tag_code for constraint in unknown] == ["need_smoking_status"]


def test_ai_suggest_action_falls_back_to_verify_task_for_invalid_structured_value():
    ext = AiExtraction(
        entity_type="memo",
        entity_id=1,
        extracted_label="drinking_status",
        extracted_value="heavy",
        confidence=90,
        extraction_type="risk",
        extraction_status="suggested",
    )
    assert _suggest_action(ext) == "create_verify_task"


def test_reserve_extraction_job_blocks_duplicate_inflight_work(db_session: Session):
    first = _reserve_extraction_job(db_session, memo_id=42)

    assert first.job_key == "memo:42"
    assert first.extracted_label == EXTRACTION_TRIGGER_LABEL
    assert first.extraction_status is None

    with pytest.raises(HTTPException) as exc_info:
        _reserve_extraction_job(db_session, memo_id=42)

    assert exc_info.value.status_code == 409
    assert "already running" in exc_info.value.detail


def test_reserve_extraction_job_replaces_stale_job(db_session: Session):
    first = _reserve_extraction_job(db_session, memo_id=99)
    first.created_at = utc_now() - timedelta(minutes=30)
    db_session.commit()

    replacement = _reserve_extraction_job(db_session, memo_id=99)

    rows = db_session.query(AiExtraction).filter(AiExtraction.job_key == "memo:99").all()
    assert len(rows) == 1
    assert rows[0].job_key == "memo:99"
    assert rows[0].created_at >= utc_now() - timedelta(minutes=1)
    assert replacement.extraction_id == rows[0].extraction_id


def test_extract_from_memo_clears_trigger_job_after_success(monkeypatch, db_session: Session):
    class FakeResponse:
        def __init__(self, content: str):
            self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse('{"observation_tags":[{"tag_code":"personality_calm","tag_value":"calm","confidence":80,"evidence":"stable"}],"risk_hints":[]}')

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    db_session.add_all([UserProfile(user_id=1), UserProfile(user_id=2)])
    db_session.flush()
    event = InteractionEvent(user_a_id=1, user_b_id=2, event_type="meet")
    db_session.add(event)
    db_session.flush()
    memo = InteractionMemo(related_event_id=event.event_id, author_id=1, raw_text="calm and polite")
    db_session.add(memo)
    db_session.commit()

    trigger_job = _reserve_extraction_job(db_session, memo_id=memo.memo_id)
    monkeypatch.setattr("app.services.llm_extraction_service._get_client", lambda: FakeClient())

    result = extract_from_memo(db_session, memo.memo_id, trigger_job_id=trigger_job.extraction_id)

    assert len(result) == 1
    rows = db_session.query(AiExtraction).order_by(AiExtraction.extraction_id.asc()).all()
    assert len(rows) == 1
    assert rows[0].job_key is None
    assert rows[0].extracted_label == "personality_calm"
    assert rows[0].extraction_status == "suggested"


def test_filter_by_hard_rules_supports_gte_and_not_in_must_preferences(db_session: Session):
    db_session.add_all(
        [
            UserProfile(user_id=1, active_status="active", open_to_match=1),
            UserProfile(user_id=2, height_cm=172, city_code="SH", active_status="active", open_to_match=1),
            UserProfile(user_id=3, height_cm=165, city_code="BJ", active_status="active", open_to_match=1),
            UserProfile(user_id=4, height_cm=180, city_code="BJ", active_status="active", open_to_match=1),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            UserPreference(
                user_id=1,
                dimension="height",
                operator="gte",
                value_json={"value": 170},
                priority_level="must",
            ),
            UserPreference(
                user_id=1,
                dimension="city",
                operator="not_in",
                value_json={"cities": ["BJ"]},
                priority_level="must",
            ),
        ]
    )
    db_session.commit()

    assert filter_by_hard_rules(db_session, requester_user_id=1) == [2]
