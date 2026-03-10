import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.models import RecommendationSnapshot, UserProfile  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a PostgreSQL migration and constraint smoke test against a disposable database.",
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="Disposable PostgreSQL database URL, e.g. postgresql+psycopg://postgres:postgres@localhost:5432/ai_match_mvp",
    )
    return parser.parse_args()


def ensure_postgresql_url(database_url: str) -> None:
    if not database_url.startswith("postgresql"):
        raise SystemExit("Expected a PostgreSQL DATABASE_URL starting with 'postgresql'.")


def run_migrations(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")


def run_smoke_checks(database_url: str) -> None:
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    base_user_id = 900_001

    try:
        dialect_name = session.execute(text("SELECT version()"))
        print(dialect_name.scalar_one())

        session.query(RecommendationSnapshot).filter(
            RecommendationSnapshot.requester_user_id.in_([base_user_id, base_user_id + 1])
        ).delete(synchronize_session=False)
        session.query(UserProfile).filter(UserProfile.user_id.in_([base_user_id, base_user_id + 1, base_user_id + 2])).delete(
            synchronize_session=False,
        )
        session.commit()

        session.add_all([
            UserProfile(user_id=base_user_id, active_status="active", open_to_match=1),
            UserProfile(user_id=base_user_id + 1, active_status="active", open_to_match=1),
        ])
        session.commit()

        session.add_all([
            RecommendationSnapshot(requester_user_id=base_user_id, candidate_user_id=base_user_id + 1, snapshot_stage="rough"),
            RecommendationSnapshot(requester_user_id=base_user_id, candidate_user_id=base_user_id + 1, snapshot_stage="rough"),
        ])
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected unique constraint on recommendation_snapshot to reject duplicates")

        session.add(UserProfile(user_id=base_user_id + 2, active_status="broken"))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected check constraint on user_profile.active_status to reject invalid values")

        print("PostgreSQL smoke test passed.")
    finally:
        session.close()
        engine.dispose()


def main() -> None:
    args = parse_args()
    ensure_postgresql_url(args.database_url)
    run_migrations(args.database_url)
    run_smoke_checks(args.database_url)


if __name__ == "__main__":
    main()