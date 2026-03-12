import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.auth import create_access_token
from app.config import Settings, get_settings
from app.main import app
from app.models import (
    AiExtraction,
    InteractionEvent,
    InteractionMemo,
    RecommendationSnapshot,
    UserPreference,
    UserConstraint,
    UserCredential,
    UserProfile,
    VerifyTask,
)
from app.services.auth_service import upsert_password_credential
from app.services.llm_extraction_service import extract_from_memo


def _load_migration_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _bearer_headers(user_id: int, role: str, settings: Settings) -> dict[str, str]:
    token = create_access_token(user_id, role, settings)
    return {"Authorization": f"Bearer {token}"}


def test_password_login_and_bearer_authorization(client, db_session: Session):
    db_session.add_all([
        UserProfile(user_id=1, active_status="active", open_to_match=1),
        UserProfile(user_id=2, active_status="active", open_to_match=1),
    ])
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "user")

    login_response = client.post("/api/auth/login", json={"userId": 1, "password": "password123"})
    assert login_response.status_code == 200
    token = login_response.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["userId"] == 1
    assert me_response.json()["role"] == "user"

    own_profile = client.get("/api/profile/1", headers=headers)
    assert own_profile.status_code == 200

    other_profile = client.get("/api/profile/2", headers=headers)
    assert other_profile.status_code == 403


def test_login_and_verify_confirmation_emit_audit_logs(client, db_session: Session, test_settings: Settings, caplog):
    db_session.add_all([
        UserProfile(user_id=1, active_status="active", open_to_match=1),
        UserProfile(user_id=2, active_status="active", open_to_match=1),
    ])
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "matchmaker")

    task = VerifyTask(
        requester_user_id=1,
        candidate_user_id=2,
        verify_field="city_code",
        task_status="pending",
    )
    db_session.add(task)
    db_session.commit()

    caplog.set_level("INFO", logger="app.audit")

    login_response = client.post("/api/auth/login", json={"userId": 1, "password": "password123"})
    assert login_response.status_code == 200

    headers = {"Authorization": f"Bearer {login_response.json()['accessToken']}"}
    confirm_response = client.post(
        f"/api/verify-tasks/{task.task_id}/confirm",
        json={"confirmedValue": "310000"},
        headers=headers,
    )
    assert confirm_response.status_code == 200

    messages = [record.getMessage() for record in caplog.records]
    assert any('"event": "user.login"' in message and '"outcome": "success"' in message for message in messages)
    assert any('"event": "verify_task.confirm"' in message and '"outcome": "success"' in message for message in messages)



def test_verify_task_confirm_conflict_returns_409_and_preserves_first_write(client, db_session: Session, test_settings: Settings):
    db_session.add_all([
        UserProfile(user_id=1, active_status="active", open_to_match=1),
        UserProfile(user_id=2, active_status="active", open_to_match=1, city_code="100000"),
    ])
    db_session.commit()

    task = VerifyTask(
        requester_user_id=1,
        candidate_user_id=2,
        verify_field="city_code",
        task_status="pending",
    )
    db_session.add(task)
    db_session.commit()

    headers = _bearer_headers(1, "matchmaker", test_settings)

    first_response = client.post(
        f"/api/verify-tasks/{task.task_id}/confirm",
        json={"confirmedValue": "310000"},
        headers=headers,
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/verify-tasks/{task.task_id}/confirm",
        json={"confirmedValue": "440100"},
        headers=headers,
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Task is not pending"

    db_session.expire_all()
    refreshed_task = db_session.query(VerifyTask).filter(VerifyTask.task_id == task.task_id).one()
    refreshed_candidate = db_session.query(UserProfile).filter(UserProfile.user_id == 2).one()

    assert refreshed_task.task_status == "confirmed"
    assert refreshed_task.confirmed_value == "310000"
    assert refreshed_candidate.city_code == "310000"

def test_non_privileged_user_cannot_escalate_role_via_credential_upsert(client, db_session: Session, test_settings: Settings):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "user")

    response = client.post(
        "/api/auth/credential",
        json={"userId": 1, "password": "new-password123", "role": "admin"},
        headers=_bearer_headers(1, "user", test_settings),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot change your own role"

    relogin_response = client.post("/api/auth/login", json={"userId": 1, "password": "password123"})
    assert relogin_response.status_code == 200

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {relogin_response.json()['accessToken']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "user"


def test_non_privileged_user_can_rotate_own_password_without_role_change(client, db_session: Session, test_settings: Settings):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "user")

    response = client.post(
        "/api/auth/credential",
        json={"userId": 1, "password": "rotated-password123", "role": "user"},
        headers=_bearer_headers(1, "user", test_settings),
    )
    assert response.status_code == 200
    assert response.json() == {"userId": 1, "role": "user"}

    old_password_response = client.post("/api/auth/login", json={"userId": 1, "password": "password123"})
    assert old_password_response.status_code == 401

    new_password_response = client.post("/api/auth/login", json={"userId": 1, "password": "rotated-password123"})
    assert new_password_response.status_code == 200


def test_non_privileged_user_cannot_update_own_verification_status(client, db_session: Session, test_settings: Settings):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "user")

    response = client.post(
        "/api/profile/1",
        json={"verification_status": "verified"},
        headers=_bearer_headers(1, "user", test_settings),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only privileged actors can update: verification_status"

    profile = db_session.query(UserProfile).filter(UserProfile.user_id == 1).one()
    assert profile.verification_status is None


def test_non_privileged_user_cannot_create_observation_tags(client, db_session: Session, test_settings: Settings):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "user")

    response = client.post(
        "/api/profile/1/observation-tag",
        json={"tag_code": "warm", "tag_value": "kind", "observer_type": "matchmaker"},
        headers=_bearer_headers(1, "user", test_settings),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Privileged role required"


def test_privileged_actor_can_create_observation_tags(client, db_session: Session, test_settings: Settings):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()

    response = client.post(
        "/api/profile/1/observation-tag",
        json={"tag_code": "warm", "tag_value": "kind", "observer_type": "matchmaker"},
        headers=_bearer_headers(1, "matchmaker", test_settings),
    )
    assert response.status_code == 200
    assert response.json()["tag_code"] == "warm"
    assert response.json()["observer_type"] == "matchmaker"


def test_constraint_creation_rejects_unsupported_field(client, db_session: Session, test_settings: Settings):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()

    response = client.post(
        "/api/profile/1/constraint",
        json={"tag_code": "bad_field", "tag_type": "verify", "applies_to_field": "favorite_color"},
        headers=_bearer_headers(1, "matchmaker", test_settings),
    )
    assert response.status_code == 422
    assert "Input should be" in response.json()["detail"][0]["msg"]


def test_recommendation_generation_ignores_legacy_invalid_verify_constraints(client, db_session: Session, test_settings: Settings):
    db_session.add_all([
        UserProfile(user_id=1, gender="male", age=30, city_code="310000", active_status="active", open_to_match=1),
        UserProfile(user_id=2, gender="female", age=28, city_code="310000", active_status="active", open_to_match=1),
    ])
    db_session.commit()

    # Legacy bad rows should not be able to break recommendation generation.
    db_session.add(
        UserConstraint(
            user_id=1,
            tag_code="legacy_bad_constraint",
            tag_type="verify",
            applies_to_field="favorite_color",
            status="active",
            constraint_scope="warning",
        )
    )
    db_session.commit()

    response = client.post(
        "/api/recommendation/generate",
        json={"requesterUserId": 1},
        headers=_bearer_headers(1, "user", test_settings),
    )
    assert response.status_code == 200
    assert len(response.json()["topCandidates"]) == 1
    assert db_session.query(VerifyTask).count() == 0


def test_verify_confirmation_rejects_invalid_enum_value(client, db_session: Session, test_settings: Settings):
    db_session.add_all([
        UserProfile(user_id=1, active_status="active", open_to_match=1),
        UserProfile(user_id=2, active_status="active", open_to_match=1),
    ])
    db_session.commit()
    upsert_password_credential(db_session, 1, "password123", "matchmaker")

    task = VerifyTask(
        requester_user_id=1,
        candidate_user_id=2,
        verify_field="smoking_status",
        task_status="pending",
    )
    db_session.add(task)
    db_session.commit()

    response = client.post(
        f"/api/verify-tasks/{task.task_id}/confirm",
        json={"confirmedValue": "heavy"},
        headers=_bearer_headers(1, "matchmaker", test_settings),
    )
    assert response.status_code == 422
    assert "must be one of" in response.json()["detail"]


def test_production_settings_reject_insecure_runtime_combinations():
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            database_url="sqlite:///./prod.db",
            jwt_secret_key="short-secret",
            auth_required=True,
            allow_legacy_headers=False,
            deepseek_api_key="configured",
        ).validate_runtime_requirements()

    with pytest.raises(ValueError):
        Settings(
            environment="production",
            database_url="sqlite:///./prod.db",
            jwt_secret_key="this-is-a-secure-secret-key-with-more-than-32-chars",
            auth_required=True,
            allow_legacy_headers=True,
            deepseek_api_key="configured",
        ).validate_runtime_requirements()

    with pytest.raises(ValueError):
        Settings(
            environment="production",
            database_url="sqlite:///./prod.db",
            jwt_secret_key="this-is-a-secure-secret-key-with-more-than-32-chars",
            auth_required=True,
            allow_legacy_headers=False,
            deepseek_api_key=None,
        ).validate_runtime_requirements()


def test_production_mode_rejects_legacy_actor_headers(client, db_session: Session):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()

    production_settings = Settings(
        environment="production",
        database_url="sqlite:///./test.db",
        auth_required=True,
        allow_legacy_headers=False,
        allow_sqlite_in_production=True,
        jwt_secret_key="this-is-a-secure-secret-key-with-more-than-32-chars",
        deepseek_api_key="configured",
    )
    app.dependency_overrides[get_settings] = lambda: production_settings

    response = client.get("/api/profile/1", headers={"X-User-Id": "1", "X-Role": "user"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Legacy actor headers are disabled"


def test_issue_token_requires_authenticated_actor_even_when_auth_optional(client, db_session: Session):
    db_session.add(UserProfile(user_id=1, active_status="active", open_to_match=1))
    db_session.commit()

    relaxed_settings = Settings(
        environment="development",
        database_url="sqlite:///./test.db",
        auth_required=False,
        allow_legacy_headers=True,
        jwt_secret_key="test-secret-key-with-32-bytes-minimum",
    )
    app.dependency_overrides[get_settings] = lambda: relaxed_settings

    response = client.post("/api/auth/token", json={"userId": 1, "role": "user"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required to issue token"


def test_ai_trigger_returns_explicit_error_when_not_configured(client, db_session: Session, test_settings: Settings):
    db_session.add_all([UserProfile(user_id=1), UserProfile(user_id=2)])
    db_session.flush()
    event = InteractionEvent(user_a_id=1, user_b_id=2, event_type="meet")
    db_session.add(event)
    db_session.flush()
    memo = InteractionMemo(related_event_id=event.event_id, author_id=1, raw_text="memo awaiting extraction")
    db_session.add(memo)
    db_session.commit()

    no_ai_settings = Settings(
        environment="development",
        database_url=test_settings.database_url,
        auth_required=True,
        allow_legacy_headers=False,
        jwt_secret_key=test_settings.jwt_secret_key,
        jwt_issuer=test_settings.jwt_issuer,
        ai_extraction_enabled=True,
        deepseek_api_key=None,
    )
    app.dependency_overrides[get_settings] = lambda: no_ai_settings

    response = client.post(
        f"/api/ai-extraction/trigger/{memo.memo_id}",
        headers=_bearer_headers(1, "matchmaker", no_ai_settings),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "AI extraction is not configured"


def test_recommendation_generation_is_idempotent(client, db_session: Session, test_settings: Settings):
    db_session.add_all([
        UserProfile(user_id=1, gender="male", age=30, city_code="310000", active_status="active", open_to_match=1),
        UserProfile(user_id=2, gender="female", age=28, city_code="310000", active_status="active", open_to_match=1),
        UserProfile(user_id=3, gender="female", age=27, city_code="310000", active_status="active", open_to_match=1),
    ])
    db_session.commit()

    db_session.add(
        UserConstraint(
            user_id=1,
            tag_code="pet_follow_up",
            tag_type="verify",
            applies_to_field="pet_status",
            status="active",
            constraint_scope="warning",
        )
    )
    db_session.commit()

    headers = _bearer_headers(1, "user", test_settings)
    payload = {"requesterUserId": 1}

    first = client.post("/api/recommendation/generate", json=payload, headers=headers)
    second = client.post("/api/recommendation/generate", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["topCandidates"]) == 2
    assert len(second.json()["topCandidates"]) == 2

    snapshots = db_session.query(RecommendationSnapshot).all()
    tasks = db_session.query(VerifyTask).all()
    assert len(snapshots) == 2
    assert len(tasks) == 2
    assert len({(row.requester_user_id, row.candidate_user_id, row.snapshot_stage) for row in snapshots}) == 2
    assert len({(row.requester_user_id, row.candidate_user_id, row.verify_field, row.task_status) for row in tasks}) == 2


def test_model_constraints_reject_invalid_values_and_duplicates(db_session: Session):
    db_session.add_all([UserProfile(user_id=1), UserProfile(user_id=2)])
    db_session.commit()

    db_session.add(UserPreference(user_id=1, dimension="invalid", operator="in"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add_all([
        AiExtraction(entity_type="memo", entity_id=1, extracted_label="job", job_key="memo:1"),
        AiExtraction(entity_type="memo", entity_id=1, extracted_label="job", job_key="memo:1"),
    ])
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add_all([
        RecommendationSnapshot(requester_user_id=1, candidate_user_id=2, snapshot_stage="rough"),
        RecommendationSnapshot(requester_user_id=1, candidate_user_id=2, snapshot_stage="rough"),
    ])
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_json_backed_tables_compile_for_postgresql():
    tables = [
        UserPreference.__table__,
        RecommendationSnapshot.__table__,
        InteractionEvent.__table__,
    ]

    for table in tables:
        compiled = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert 'JSON' in compiled
        assert 'sqlite' not in compiled.lower()


def test_sqlite_only_autoincrement_migrations_noop_on_postgresql(monkeypatch):
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_files = [
        versions_dir / "fix_sqlite_autoincrement.py",
        versions_dir / "fix_preference_autoincrement.py",
    ]

    for migration_file in migration_files:
        module = _load_migration_module(migration_file)
        recorded_sql: list[str] = []
        monkeypatch.setattr(
            module.op,
            "get_context",
            lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        )
        monkeypatch.setattr(module.op, "execute", lambda sql: recorded_sql.append(sql))

        module.upgrade()
        assert recorded_sql == []


def test_sqlite_foreign_key_helpers_only_emit_pragma_for_sqlite(monkeypatch):
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_files = [
        versions_dir / "enforce_foreign_keys.py",
        versions_dir / "harden_constraints_auth.py",
    ]

    for migration_file in migration_files:
        module = _load_migration_module(migration_file)
        recorded_sql: list[str] = []

        monkeypatch.setattr(
            module.op,
            "get_context",
            lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        )
        monkeypatch.setattr(module.op, "execute", lambda sql: recorded_sql.append(sql))
        module._set_sqlite_foreign_keys(True)
        assert recorded_sql == []

        monkeypatch.setattr(
            module.op,
            "get_context",
            lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        )
        module._set_sqlite_foreign_keys(False)
        assert recorded_sql == ["PRAGMA foreign_keys=OFF"]


def test_extraction_failure_is_persisted(monkeypatch, db_session: Session):
    class FakeResponse:
        def __init__(self, content: str):
            self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse("not json")

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    db_session.add_all([
        UserProfile(user_id=1),
        UserProfile(user_id=2),
    ])
    db_session.flush()
    event = InteractionEvent(user_a_id=1, user_b_id=2, event_type="meet")
    db_session.add(event)
    db_session.flush()
    memo = InteractionMemo(related_event_id=event.event_id, author_id=1, raw_text="first meeting memo")
    db_session.add(memo)
    db_session.commit()

    monkeypatch.setattr("app.services.llm_extraction_service._get_client", lambda: FakeClient())

    result = extract_from_memo(db_session, memo.memo_id)
    assert result == []

    rows = db_session.query(AiExtraction).all()
    assert len(rows) == 1
    assert rows[0].extraction_status == "failed"
    assert rows[0].extracted_label == "parse_error"


def test_missing_ai_configuration_is_persisted_as_failure(monkeypatch, db_session: Session):
    db_session.add_all([
        UserProfile(user_id=1),
        UserProfile(user_id=2),
    ])
    db_session.flush()
    event = InteractionEvent(user_a_id=1, user_b_id=2, event_type="meet")
    db_session.add(event)
    db_session.flush()
    memo = InteractionMemo(related_event_id=event.event_id, author_id=1, raw_text="memo without ai key")
    db_session.add(memo)
    db_session.commit()

    monkeypatch.setattr("app.services.llm_extraction_service._get_client", lambda: None)

    result = extract_from_memo(db_session, memo.memo_id)
    assert result == []

    rows = db_session.query(AiExtraction).all()
    assert len(rows) == 1
    assert rows[0].extraction_status == "failed"
    assert rows[0].extracted_label == "config_error"


def test_alembic_upgrade_head_enforces_new_schema(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "migrated.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    backend_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))
    alembic_cfg.set_main_option("prepend_sys_path", str(backend_root))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    inspector = sa.inspect(engine)
    assert "user_credential" in inspector.get_table_names()

    MigratedSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = MigratedSession()
    try:
        session.add_all([UserProfile(user_id=1), UserProfile(user_id=2)])
        session.commit()

        session.add(UserCredential(user_id=1, role="user", password_hash="hash", password_salt="salt"))
        session.commit()

        session.add_all([
            RecommendationSnapshot(requester_user_id=1, candidate_user_id=2, snapshot_stage="rough"),
            RecommendationSnapshot(requester_user_id=1, candidate_user_id=2, snapshot_stage="rough"),
        ])
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(UserProfile(user_id=3, active_status="broken"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add_all([
            AiExtraction(entity_type="memo", entity_id=1, extracted_label="job", job_key="memo:1"),
            AiExtraction(entity_type="memo", entity_id=1, extracted_label="job", job_key="memo:1"),
        ])
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
        engine.dispose()
        get_settings.cache_clear()
