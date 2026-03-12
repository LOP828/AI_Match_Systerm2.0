"""Tests for the verified-stage recommendation regeneration flow."""

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import Settings
from app.models import UserConstraint, UserProfile, VerifyTask
from app.services.auth_service import upsert_password_credential
from app.services.recommendation_service import regenerate_candidates


def _bearer_headers(user_id: int, role: str, settings: Settings) -> dict[str, str]:
    token = create_access_token(user_id, role, settings)
    return {"Authorization": f"Bearer {token}"}


def _seed_profiles(db: Session) -> None:
    """Create a requester (id=1) and several candidate profiles."""
    db.add_all(
        [
            UserProfile(
                user_id=1,
                gender="male",
                age=28,
                height_cm=175,
                city_code="SH",
                education_level="bachelor",
                marital_status="single",
                smoking_status="no",
                drinking_status="sometimes",
                pet_status="no_pet",
                active_status="active",
                open_to_match=1,
            ),
            UserProfile(
                user_id=2,
                gender="female",
                age=26,
                height_cm=165,
                city_code="SH",
                education_level="bachelor",
                marital_status="single",
                smoking_status="no",
                drinking_status="no",
                pet_status="no_pet",
                active_status="active",
                open_to_match=1,
            ),
            UserProfile(
                user_id=3,
                gender="female",
                age=30,
                height_cm=160,
                city_code="BJ",
                education_level="master",
                marital_status="single",
                smoking_status="no",
                drinking_status="no",
                pet_status="has_cat",
                active_status="active",
                open_to_match=1,
            ),
        ]
    )
    db.commit()


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


def test_regenerate_no_confirmed_tasks(db_session: Session):
    """regenerate works even with zero confirmed verify tasks."""
    _seed_profiles(db_session)
    result = regenerate_candidates(db_session, requester_user_id=1)

    assert result["requesterId"] == 1
    assert result["stage"] == "verified"
    assert result["usedConfirmedVerifyTasks"] == 0
    assert len(result["items"]) > 0


def test_regenerate_with_confirmed_tasks(db_session: Session):
    """After confirming a verify task, regenerate picks up updated data."""
    _seed_profiles(db_session)

    # Create and confirm a verify task
    task = VerifyTask(
        requester_user_id=1,
        candidate_user_id=2,
        verify_field="city_code",
        trigger_reason="test",
        task_status="pending",
    )
    db_session.add(task)
    db_session.commit()

    # Simulate confirm: update profile and task status
    candidate = db_session.query(UserProfile).filter(UserProfile.user_id == 2).first()
    candidate.city_code = "SH"
    task.task_status = "confirmed"
    task.confirmed_value = "SH"
    db_session.commit()

    result = regenerate_candidates(db_session, requester_user_id=1)
    assert result["usedConfirmedVerifyTasks"] == 1
    assert result["stage"] == "verified"
    assert len(result["items"]) > 0


def test_regenerate_counts_only_considered_confirmed_tasks(db_session: Session):
    """usedConfirmedVerifyTasks should only count confirmations on candidates that actually enter rerank."""
    _seed_profiles(db_session)
    db_session.add(
        UserProfile(
            user_id=4,
            gender="female",
            age=29,
            active_status="inactive",
            open_to_match=0,
        )
    )
    db_session.commit()

    db_session.add_all(
        [
            VerifyTask(
                requester_user_id=1,
                candidate_user_id=2,
                verify_field="city_code",
                trigger_reason="used",
                task_status="confirmed",
                confirmed_value="SH",
            ),
            VerifyTask(
                requester_user_id=1,
                candidate_user_id=4,
                verify_field="city_code",
                trigger_reason="unused",
                task_status="confirmed",
                confirmed_value="GZ",
            ),
        ]
    )
    db_session.commit()

    result = regenerate_candidates(db_session, requester_user_id=1)
    assert result["usedConfirmedVerifyTasks"] == 1


def test_regenerate_nonexistent_requester(db_session: Session):
    """regenerate for a non-existent user returns empty items."""
    result = regenerate_candidates(db_session, requester_user_id=999)
    assert result["items"] == []
    assert result["usedConfirmedVerifyTasks"] == 0


# ---------------------------------------------------------------------------
# API-layer tests
# ---------------------------------------------------------------------------


def test_regenerate_api_endpoint(client, db_session: Session, test_settings: Settings):
    """POST /api/recommendation/regenerate/{id} returns 200."""
    _seed_profiles(db_session)
    upsert_password_credential(db_session, 1, "pass", "matchmaker")
    headers = _bearer_headers(1, "matchmaker", test_settings)

    resp = client.post("/api/recommendation/regenerate/1", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "verified"
    assert "usedConfirmedVerifyTasks" in body
    assert isinstance(body["items"], list)


def test_confirm_response_enhanced(client, db_session: Session, test_settings: Settings):
    """POST /verify-tasks/{id}/confirm returns enhanced response fields."""
    _seed_profiles(db_session)
    upsert_password_credential(db_session, 1, "pass", "matchmaker")
    headers = _bearer_headers(1, "matchmaker", test_settings)

    task = VerifyTask(
        requester_user_id=1,
        candidate_user_id=2,
        verify_field="city_code",
        trigger_reason="test",
        task_status="pending",
    )
    db_session.add(task)
    db_session.commit()
    task_id = task.task_id

    resp = client.post(
        f"/api/verify-tasks/{task_id}/confirm",
        json={"confirmedValue": "BJ"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["writtenField"] == "city_code"
    assert body["writtenValue"] == "BJ"
    assert "pendingCount" in body
    assert "confirmedCount" in body
    assert "shouldRegenerateRecommendation" in body
