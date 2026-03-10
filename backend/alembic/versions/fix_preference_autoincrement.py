"""fix user_preference autoincrement for SQLite

Revision ID: fix_pref_auto
Revises: fix_sqlite_auto
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "fix_pref_auto"
down_revision: Union[str, None] = "fix_sqlite_auto"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_context().dialect.name == "sqlite"


def upgrade() -> None:
    if not _is_sqlite():
        return

    op.execute("PRAGMA foreign_keys=OFF")
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
        INSERT INTO user_preference_new (user_id, dimension, operator, value_json, priority_level, source_type, confirmed_by_matchmaker, created_at, updated_at)
        SELECT user_id, dimension, operator, value_json, priority_level, source_type, confirmed_by_matchmaker, created_at, updated_at
        FROM user_preference
    """)
    op.execute("DROP TABLE user_preference")
    op.execute("ALTER TABLE user_preference_new RENAME TO user_preference")
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    pass
