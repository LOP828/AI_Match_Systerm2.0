"""Tests for Phase 3: feedback loop — structured feedback, history, signals, recommendation correction."""

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import Settings
from app.models import InteractionEvent, UserProfile
from app.services.auth_service import upsert_password_credential
from app.services.feedback_service import get_feedback_signals
from app.services.recommendation_service import _feedback_adjustment


def _bearer_headers(user_id: int, role: str, settings: Settings) -> dict[str, str]:
    token = create_access_token(user_id, role, settings)
    return {"Authorization": f"Bearer {token}"}


def _seed_users(db: Session) -> None:
    """Create test users 1, 2, 10 (admin/matchmaker)."""
    db.add_all(
        [
            UserProfile(user_id=1, gender="male", age=28, active_status="active", open_to_match=1),
            UserProfile(user_id=2, gender="female", age=26, active_status="active", open_to_match=1),
            UserProfile(user_id=10, active_status="active", open_to_match=1),
        ]
    )
    db.flush()


def test_record_meeting_with_structured_fields(client, db_session: Session, test_settings: Settings):
    """POST /feedback/meeting with structured feedback fields stores them correctly."""
    _seed_users(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    resp = client.post(
        "/api/feedback/meeting",
        json={
            "userAId": 1,
            "userBId": 2,
            "willingnessA": "yes",
            "willingnessB": "no",
            "conversationSmoothness": 4,
            "appearanceAcceptance": 3,
            "valuesAlignment": 5,
            "rejectReasonPrimary": "distance_too_far",
            "rejectReasonSecondary": "schedule_conflict",
            "memoText": "They met at a cafe, A liked B but B felt distance is an issue.",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["eventId"] > 0

    event = db_session.query(InteractionEvent).filter(
        InteractionEvent.event_id == body["eventId"]
    ).first()
    assert event is not None
    assert event.conversation_smoothness == 4
    assert event.appearance_acceptance == 3
    assert event.values_alignment == 5
    assert event.reject_reason_primary == "distance_too_far"
    assert event.reject_reason_secondary == "schedule_conflict"


def test_non_privileged_user_cannot_record_meeting(client, db_session: Session, test_settings: Settings):
    _seed_users(db_session)
    upsert_password_credential(db_session, 1, "password123", "user")
    headers = _bearer_headers(1, "user", test_settings)

    resp = client.post(
        "/api/feedback/meeting",
        json={
            "userAId": 1,
            "userBId": 2,
            "willingnessA": "yes",
            "willingnessB": "yes",
            "memoText": "unauthorized write",
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Privileged role required"


def test_record_meeting_rejects_same_user_pair(client, db_session: Session, test_settings: Settings):
    _seed_users(db_session)
    upsert_password_credential(db_session, 10, "password123", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    resp = client.post(
        "/api/feedback/meeting",
        json={
            "userAId": 1,
            "userBId": 1,
            "willingnessA": "yes",
            "willingnessB": "yes",
            "memoText": "invalid self pair",
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "must be different" in resp.json()["detail"][0]["msg"]


def test_get_user_history_returns_structured_fields(client, db_session: Session, test_settings: Settings):
    """GET /feedback/history/{user_id} returns events with structured feedback fields."""
    _seed_users(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    # Record two meetings
    client.post(
        "/api/feedback/meeting",
        json={"userAId": 1, "userBId": 2, "willingnessA": "yes", "willingnessB": "yes",
              "conversationSmoothness": 5, "valuesAlignment": 4, "memoText": "Great meeting"},
        headers=headers,
    )
    client.post(
        "/api/feedback/meeting",
        json={"userAId": 2, "userBId": 1, "willingnessA": "no", "willingnessB": "yes",
              "appearanceAcceptance": 2, "rejectReasonPrimary": "no_chemistry", "memoText": "Not good"},
        headers=headers,
    )

    resp = client.get("/api/feedback/history/1", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    # Check that structured fields are present in at least one item
    smoothness_values = [i.get("conversation_smoothness") for i in items if i.get("conversation_smoothness")]
    assert 5 in smoothness_values

    reject_reasons = [i.get("reject_reason_primary") for i in items if i.get("reject_reason_primary")]
    assert "no_chemistry" in reject_reasons


def test_get_feedback_signals_aggregation(client, db_session: Session, test_settings: Settings):
    """GET /feedback/signals/{user_id} returns correct aggregated data."""
    _seed_users(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    # Record 3 meetings for user 2
    meetings = [
        {"userAId": 1, "userBId": 2, "willingnessA": "yes", "willingnessB": "yes",
         "conversationSmoothness": 4, "appearanceAcceptance": 5, "valuesAlignment": 3, "memoText": "m1"},
        {"userAId": 1, "userBId": 2, "willingnessA": "yes", "willingnessB": "no",
         "conversationSmoothness": 2, "appearanceAcceptance": 3, "valuesAlignment": 1,
         "rejectReasonPrimary": "no_chemistry", "memoText": "m2"},
        {"userAId": 1, "userBId": 2, "willingnessA": "no", "willingnessB": "yes",
         "conversationSmoothness": 3, "rejectReasonPrimary": "distance_too_far",
         "rejectReasonSecondary": "no_chemistry", "memoText": "m3"},
    ]
    for m in meetings:
        resp = client.post("/api/feedback/meeting", json=m, headers=headers)
        assert resp.status_code == 200

    resp = client.get("/api/feedback/signals/2", headers=headers)
    assert resp.status_code == 200
    signals = resp.json()

    assert signals["userId"] == 2
    assert signals["totalMeetings"] == 3

    # avgConversationSmoothness: (4+2+3)/3 = 3.0
    assert signals["avgConversationSmoothness"] == 3.0
    # avgAppearanceAcceptance: (5+3)/2 = 4.0 (only 2 have values)
    assert signals["avgAppearanceAcceptance"] == 4.0
    # avgValuesAlignment: (3+1)/2 = 2.0
    assert signals["avgValuesAlignment"] == 2.0

    # continueRate for user 2 (B side): yes, no, yes → 2/3 ≈ 0.67
    assert signals["continueRate"] == pytest.approx(0.67, abs=0.01)

    # topRejectReasons: "no_chemistry" appears 2x, "distance_too_far" 1x
    assert signals["topRejectReasons"][0] == "no_chemistry"
    assert "distance_too_far" in signals["topRejectReasons"]


def test_feedback_signals_empty(client, db_session: Session, test_settings: Settings):
    """Signals for user with no meetings returns zeros/nulls."""
    _seed_users(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    resp = client.get("/api/feedback/signals/1", headers=headers)
    assert resp.status_code == 200
    signals = resp.json()

    assert signals["totalMeetings"] == 0
    assert signals["avgConversationSmoothness"] is None
    assert signals["continueRate"] is None
    assert signals["topRejectReasons"] == []


def test_feedback_adjustment_with_data(db_session: Session):
    """_feedback_adjustment returns non-zero value when feedback exists."""
    # High continue rate + high ratings → positive adjustment
    signals_positive = {
        "userId": 1,
        "totalMeetings": 5,
        "avgConversationSmoothness": 4.5,
        "avgAppearanceAcceptance": 4.0,
        "avgValuesAlignment": 4.5,
        "topRejectReasons": [],
        "continueRate": 0.8,
    }
    adj = _feedback_adjustment(signals_positive)
    assert adj > 0, f"Expected positive adjustment, got {adj}"

    # Low continue rate + low ratings → negative adjustment
    signals_negative = {
        "userId": 2,
        "totalMeetings": 5,
        "avgConversationSmoothness": 1.5,
        "avgAppearanceAcceptance": 2.0,
        "avgValuesAlignment": 1.5,
        "topRejectReasons": ["no_chemistry"],
        "continueRate": 0.1,
    }
    adj_neg = _feedback_adjustment(signals_negative)
    assert adj_neg < 0, f"Expected negative adjustment, got {adj_neg}"


def test_feedback_adjustment_no_meetings():
    """_feedback_adjustment returns 0 when no meetings exist."""
    signals = {
        "userId": 1,
        "totalMeetings": 0,
        "avgConversationSmoothness": None,
        "avgAppearanceAcceptance": None,
        "avgValuesAlignment": None,
        "topRejectReasons": [],
        "continueRate": None,
    }
    assert _feedback_adjustment(signals) == 0.0


def test_get_feedback_signals_service_direct(db_session: Session):
    """Test get_feedback_signals service function directly."""
    _seed_users(db_session)

    # Add events directly
    db_session.add(InteractionEvent(
        user_a_id=1, user_b_id=2, event_type="meet",
        willingness_a="yes", willingness_b="yes",
        conversation_smoothness=5, appearance_acceptance=4, values_alignment=5,
    ))
    db_session.add(InteractionEvent(
        user_a_id=1, user_b_id=2, event_type="meet",
        willingness_a="no", willingness_b="no",
        conversation_smoothness=1, appearance_acceptance=1, values_alignment=1,
        reject_reason_primary="looks", reject_reason_secondary="values",
    ))
    db_session.commit()

    signals = get_feedback_signals(db_session, 2)
    assert signals["totalMeetings"] == 2
    assert signals["avgConversationSmoothness"] == 3.0  # (5+1)/2
    assert signals["avgAppearanceAcceptance"] == 2.5  # (4+1)/2
    assert signals["avgValuesAlignment"] == 3.0  # (5+1)/2
    assert signals["continueRate"] == 0.5  # 1 yes out of 2
    assert "looks" in signals["topRejectReasons"]
    assert "values" in signals["topRejectReasons"]
