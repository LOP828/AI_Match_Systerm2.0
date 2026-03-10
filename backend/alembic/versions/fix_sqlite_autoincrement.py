"""fix sqlite autoincrement for user_constraint and user_observation_tag

Revision ID: fix_sqlite_auto
Revises: 3c22fa465150
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fix_sqlite_auto"
down_revision: Union[str, None] = "3c22fa465150"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_context().dialect.name == "sqlite"


def upgrade() -> None:
    if not _is_sqlite():
        return

    # SQLite: recreate tables with INTEGER PRIMARY KEY AUTOINCREMENT for autoincrement columns
    op.execute("PRAGMA foreign_keys=OFF")

    # user_preference
    op.execute("""
        CREATE TABLE user_preference_new (
            preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            dimension VARCHAR(64) NOT NULL,
            operator VARCHAR(16) NOT NULL,
            value_json JSON,
            priority_level VARCHAR(16),
            source_type VARCHAR(32),
            confirmed_by_matchmaker BIGINT,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL
        )
    """)
    op.execute("""
        INSERT INTO user_preference_new SELECT * FROM user_preference
    """)
    op.execute("DROP TABLE user_preference")
    op.execute("ALTER TABLE user_preference_new RENAME TO user_preference")
    op.execute("""
        CREATE TABLE user_constraint_new (
            constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            tag_code VARCHAR(64) NOT NULL,
            tag_type VARCHAR(16) NOT NULL,
            direction VARCHAR(16),
            confidence NUMERIC(5,2),
            source_type VARCHAR(32),
            source_ref_id BIGINT,
            is_human_confirmed BIGINT,
            status VARCHAR(16),
            constraint_scope VARCHAR(32),
            applies_to_field VARCHAR(64),
            confirm_required BIGINT,
            updated_by BIGINT,
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL
        )
    """)
    op.execute("""
        INSERT INTO user_constraint_new (user_id, tag_code, tag_type, direction, confidence, source_type,
            source_ref_id, is_human_confirmed, status, constraint_scope, applies_to_field, confirm_required, updated_by, updated_at)
        SELECT user_id, tag_code, tag_type, direction, confidence, source_type, source_ref_id, is_human_confirmed,
            status, constraint_scope, applies_to_field, confirm_required, updated_by, updated_at
        FROM user_constraint
    """)
    op.execute("DROP TABLE user_constraint")
    op.execute("ALTER TABLE user_constraint_new RENAME TO user_constraint")

    # Same for user_observation_tag
    op.execute("""
        CREATE TABLE user_observation_tag_new (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            tag_code VARCHAR(64) NOT NULL,
            tag_value VARCHAR(64),
            confidence NUMERIC(5,2),
            observer_type VARCHAR(16),
            source_ref_id BIGINT,
            valid_from DATETIME,
            valid_to DATETIME,
            status VARCHAR(16),
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL
        )
    """)
    op.execute("""
        INSERT INTO user_observation_tag_new (user_id, tag_code, tag_value, confidence, observer_type,
            source_ref_id, valid_from, valid_to, status, created_at, updated_at)
        SELECT user_id, tag_code, tag_value, confidence, observer_type, source_ref_id, valid_from, valid_to,
            status, created_at, updated_at
        FROM user_observation_tag
    """)
    op.execute("DROP TABLE user_observation_tag")
    op.execute("ALTER TABLE user_observation_tag_new RENAME TO user_observation_tag")
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    pass


# Note: Run "alembic downgrade fix_sqlite_auto" then "alembic upgrade head" if you need to re-run
