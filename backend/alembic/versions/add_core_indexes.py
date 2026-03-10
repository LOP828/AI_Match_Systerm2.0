"""add core query indexes

Revision ID: add_core_indexes
Revises: fix_pref_auto
Create Date: 2026-03-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "add_core_indexes"
down_revision: Union[str, None] = "fix_pref_auto"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_ai_extraction_lookup", "ai_extraction", ["entity_type", "entity_id", "extraction_status"])
    op.create_index("ix_interaction_event_pair_ab", "interaction_event", ["user_a_id", "user_b_id", "event_time"])
    op.create_index("ix_interaction_event_pair_ba", "interaction_event", ["user_b_id", "user_a_id", "event_time"])
    op.create_index("ix_interaction_memo_event", "interaction_memo", ["related_event_id"])
    op.create_index("ix_recommendation_snapshot_feed", "recommendation_snapshot", ["requester_user_id", "snapshot_stage", "created_at"])
    op.create_index("ix_user_constraint_lookup", "user_constraint", ["user_id", "tag_type", "status"])
    op.create_index("ix_user_observation_tag_user", "user_observation_tag", ["user_id", "status"])
    op.create_index("ix_user_preference_lookup", "user_preference", ["user_id", "priority_level"])
    op.create_index("ix_user_profile_match_pool", "user_profile", ["active_status", "open_to_match"])
    op.create_index("ix_verify_task_feed", "verify_task", ["requester_user_id", "task_status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_verify_task_feed", table_name="verify_task")
    op.drop_index("ix_user_profile_match_pool", table_name="user_profile")
    op.drop_index("ix_user_preference_lookup", table_name="user_preference")
    op.drop_index("ix_user_observation_tag_user", table_name="user_observation_tag")
    op.drop_index("ix_user_constraint_lookup", table_name="user_constraint")
    op.drop_index("ix_recommendation_snapshot_feed", table_name="recommendation_snapshot")
    op.drop_index("ix_interaction_memo_event", table_name="interaction_memo")
    op.drop_index("ix_interaction_event_pair_ba", table_name="interaction_event")
    op.drop_index("ix_interaction_event_pair_ab", table_name="interaction_event")
    op.drop_index("ix_ai_extraction_lookup", table_name="ai_extraction")
