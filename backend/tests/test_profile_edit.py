"""Tests for Phase 4: profile editing — add/delete preference, constraint, observation tag."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import Settings
from app.models import UserConstraint, UserObservationTag, UserPreference, UserProfile
from app.services.auth_service import upsert_password_credential


def _bearer_headers(user_id: int, role: str, settings: Settings) -> dict[str, str]:
    token = create_access_token(user_id, role, settings)
    return {"Authorization": f"Bearer {token}"}


def _seed(db: Session) -> None:
    db.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db.add(UserProfile(user_id=10, active_status="active", open_to_match=1))
    db.flush()


def test_add_and_delete_preference(client, db_session: Session, test_settings: Settings):
    """Can add a preference then delete it."""
    _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    # Add
    resp = client.post(
        "/api/profile/1/preference",
        json={"dimension": "age", "operator": "between", "value_json": {"min": 25, "max": 35}, "priority_level": "must"},
        headers=headers,
    )
    assert resp.status_code == 200
    pref_id = resp.json()["preference_id"]
    assert pref_id > 0

    # Verify in DB
    pref = db_session.query(UserPreference).filter(UserPreference.preference_id == pref_id).first()
    assert pref is not None
    assert pref.dimension == "age"

    # Delete
    resp = client.delete(f"/api/profile/1/preference/{pref_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify deleted
    pref = db_session.query(UserPreference).filter(UserPreference.preference_id == pref_id).first()
    assert pref is None


def test_add_and_delete_constraint(client, db_session: Session, test_settings: Settings):
    """Can add a constraint then delete it."""
    _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    # Add
    resp = client.post(
        "/api/profile/1/constraint",
        json={"tag_code": "no_smoking", "tag_type": "block", "applies_to_field": "smoking_status"},
        headers=headers,
    )
    assert resp.status_code == 200
    cid = resp.json()["constraint_id"]

    # Delete
    resp = client.delete(f"/api/profile/1/constraint/{cid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify deleted
    assert db_session.query(UserConstraint).filter(UserConstraint.constraint_id == cid).first() is None


def test_add_and_delete_observation_tag(client, db_session: Session, test_settings: Settings):
    """Can add an observation tag then delete it (requires privileged role)."""
    _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    # Add
    resp = client.post(
        "/api/profile/1/observation-tag",
        json={"tag_code": "personality_kind", "tag_value": "kind", "confidence": 85, "observer_type": "matchmaker"},
        headers=headers,
    )
    assert resp.status_code == 200
    tag_id = resp.json()["tag_id"]

    # Delete
    resp = client.delete(f"/api/profile/1/observation-tag/{tag_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    assert db_session.query(UserObservationTag).filter(UserObservationTag.tag_id == tag_id).first() is None


def test_delete_nonexistent_returns_404(client, db_session: Session, test_settings: Settings):
    """Deleting a non-existent item returns 404."""
    _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    assert client.delete("/api/profile/1/preference/999", headers=headers).status_code == 404
    assert client.delete("/api/profile/1/constraint/999", headers=headers).status_code == 404
    assert client.delete("/api/profile/1/observation-tag/999", headers=headers).status_code == 404


def test_profile_update_basic_fields(client, db_session: Session, test_settings: Settings):
    """Can update basic profile fields."""
    _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    resp = client.post(
        "/api/profile/1",
        json={"age": 30, "city_code": "shanghai", "smoking_status": "no"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["age"] == 30
    assert body["city_code"] == "shanghai"
    assert body["smoking_status"] == "no"


def test_profile_full_response_includes_all_sections(client, db_session: Session, test_settings: Settings):
    """GET profile returns profile + preferences + constraints + tags."""
    _seed(db_session)
    upsert_password_credential(db_session, 10, "pass", "admin")
    headers = _bearer_headers(10, "admin", test_settings)

    # Add one of each
    client.post("/api/profile/1/preference",
                json={"dimension": "height", "operator": "gte", "value_json": {"value": 170}},
                headers=headers)
    client.post("/api/profile/1/constraint",
                json={"tag_code": "no_pet", "tag_type": "verify", "applies_to_field": "pet_status"},
                headers=headers)
    client.post("/api/profile/1/observation-tag",
                json={"tag_code": "trait_funny", "observer_type": "matchmaker"},
                headers=headers)

    resp = client.get("/api/profile/1", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["profile"] is not None
    assert len(body["preferences"]) >= 1
    assert len(body["constraints"]) >= 1
    assert len(body["tags"]) >= 1
