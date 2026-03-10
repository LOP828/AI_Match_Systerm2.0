"""enforce foreign keys on core relational tables

Revision ID: enforce_foreign_keys
Revises: add_core_indexes
Create Date: 2026-03-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "enforce_foreign_keys"
down_revision: Union[str, None] = "add_core_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_context().dialect.name == "sqlite"


def _set_sqlite_foreign_keys(enabled: bool) -> None:
    if _is_sqlite():
        op.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _cleanup_orphans() -> None:
    # Remove rows that would violate FK constraints.
    op.execute(
        "DELETE FROM user_preference "
        "WHERE user_id NOT IN (SELECT user_id FROM user_profile)"
    )
    op.execute(
        "DELETE FROM user_constraint "
        "WHERE user_id NOT IN (SELECT user_id FROM user_profile)"
    )
    op.execute(
        "DELETE FROM user_observation_tag "
        "WHERE user_id NOT IN (SELECT user_id FROM user_profile)"
    )
    op.execute(
        "DELETE FROM interaction_event "
        "WHERE user_a_id NOT IN (SELECT user_id FROM user_profile) "
        "OR user_b_id NOT IN (SELECT user_id FROM user_profile) "
        "OR (created_by IS NOT NULL AND created_by NOT IN (SELECT user_id FROM user_profile))"
    )
    op.execute(
        "DELETE FROM interaction_memo "
        "WHERE related_event_id NOT IN (SELECT event_id FROM interaction_event) "
        "OR author_id NOT IN (SELECT user_id FROM user_profile)"
    )
    op.execute(
        "DELETE FROM recommendation_snapshot "
        "WHERE requester_user_id NOT IN (SELECT user_id FROM user_profile) "
        "OR candidate_user_id NOT IN (SELECT user_id FROM user_profile)"
    )
    op.execute(
        "DELETE FROM verify_task "
        "WHERE requester_user_id NOT IN (SELECT user_id FROM user_profile) "
        "OR candidate_user_id NOT IN (SELECT user_id FROM user_profile)"
    )
    op.execute(
        "UPDATE ai_extraction SET reviewed_by = NULL "
        "WHERE reviewed_by IS NOT NULL "
        "AND reviewed_by NOT IN (SELECT user_id FROM user_profile)"
    )


def upgrade() -> None:
    _set_sqlite_foreign_keys(False)
    _cleanup_orphans()

    with op.batch_alter_table("user_preference") as batch_op:
        batch_op.create_foreign_key(
            "fk_user_preference_user_profile",
            "user_profile",
            ["user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("user_constraint") as batch_op:
        batch_op.create_foreign_key(
            "fk_user_constraint_user_profile",
            "user_profile",
            ["user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("user_observation_tag") as batch_op:
        batch_op.create_foreign_key(
            "fk_user_observation_tag_user_profile",
            "user_profile",
            ["user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("interaction_event") as batch_op:
        batch_op.create_foreign_key(
            "fk_interaction_event_user_a",
            "user_profile",
            ["user_a_id"],
            ["user_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_interaction_event_user_b",
            "user_profile",
            ["user_b_id"],
            ["user_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_interaction_event_created_by",
            "user_profile",
            ["created_by"],
            ["user_id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("interaction_memo") as batch_op:
        batch_op.create_foreign_key(
            "fk_interaction_memo_event",
            "interaction_event",
            ["related_event_id"],
            ["event_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_interaction_memo_author",
            "user_profile",
            ["author_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("recommendation_snapshot") as batch_op:
        batch_op.create_foreign_key(
            "fk_recommendation_snapshot_requester",
            "user_profile",
            ["requester_user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_recommendation_snapshot_candidate",
            "user_profile",
            ["candidate_user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("verify_task") as batch_op:
        batch_op.create_foreign_key(
            "fk_verify_task_requester",
            "user_profile",
            ["requester_user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_verify_task_candidate",
            "user_profile",
            ["candidate_user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.create_foreign_key(
            "fk_ai_extraction_reviewed_by",
            "user_profile",
            ["reviewed_by"],
            ["user_id"],
            ondelete="SET NULL",
        )

    _set_sqlite_foreign_keys(True)


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)

    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.drop_constraint("fk_ai_extraction_reviewed_by", type_="foreignkey")

    with op.batch_alter_table("verify_task") as batch_op:
        batch_op.drop_constraint("fk_verify_task_candidate", type_="foreignkey")
        batch_op.drop_constraint("fk_verify_task_requester", type_="foreignkey")

    with op.batch_alter_table("recommendation_snapshot") as batch_op:
        batch_op.drop_constraint("fk_recommendation_snapshot_candidate", type_="foreignkey")
        batch_op.drop_constraint("fk_recommendation_snapshot_requester", type_="foreignkey")

    with op.batch_alter_table("interaction_memo") as batch_op:
        batch_op.drop_constraint("fk_interaction_memo_author", type_="foreignkey")
        batch_op.drop_constraint("fk_interaction_memo_event", type_="foreignkey")

    with op.batch_alter_table("interaction_event") as batch_op:
        batch_op.drop_constraint("fk_interaction_event_created_by", type_="foreignkey")
        batch_op.drop_constraint("fk_interaction_event_user_b", type_="foreignkey")
        batch_op.drop_constraint("fk_interaction_event_user_a", type_="foreignkey")

    with op.batch_alter_table("user_observation_tag") as batch_op:
        batch_op.drop_constraint("fk_user_observation_tag_user_profile", type_="foreignkey")

    with op.batch_alter_table("user_constraint") as batch_op:
        batch_op.drop_constraint("fk_user_constraint_user_profile", type_="foreignkey")

    with op.batch_alter_table("user_preference") as batch_op:
        batch_op.drop_constraint("fk_user_preference_user_profile", type_="foreignkey")

    _set_sqlite_foreign_keys(True)
