from collections.abc import Generator
from pathlib import Path
import sys

import anyio
import anyio.to_thread
import pytest
import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings, get_settings
from app.db import get_db
from app.main import app
from app.models import Base


class SyncASGIClient:
    def __init__(self, asgi_app, after_request=None):
        self._app = asgi_app
        self._after_request = after_request

    def request(self, method: str, url: str, **kwargs):
        async def _request():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=20.0) as client:
                return await client.request(method, url, **kwargs)

        try:
            return anyio.run(_request)
        finally:
            if self._after_request is not None:
                self._after_request()

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)


@pytest.fixture(autouse=True)
def inline_threadpool(monkeypatch):
    async def run_sync_inline(func, *args, **kwargs):
        kwargs.pop("limiter", None)
        kwargs.pop("abandon_on_cancel", None)
        kwargs.pop("cancellable", None)
        return func(*args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        database_url="sqlite:///./unused-test.db",
        auth_required=True,
        allow_legacy_headers=False,
        jwt_secret_key="test-secret-key-with-32-bytes-minimum",
        jwt_issuer="test-suite",
        jwt_expire_minutes=30,
    )


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, test_settings: Settings) -> Generator[SyncASGIClient, None, None]:
    RequestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )

    def override_get_db() -> Generator[Session, None, None]:
        request_session = RequestSessionLocal()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    yield SyncASGIClient(app, after_request=db_session.expire_all)

    app.dependency_overrides.clear()
    get_settings.cache_clear()
