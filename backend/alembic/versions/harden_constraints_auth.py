"""add credentials and enforce enum/unique constraints

Revision ID: harden_constraints_auth
Revises: enforce_foreign_keys
Create Date: 2026-03-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "harden_constraints_auth"
down_revision: Union[str, None] = "enforce_foreign_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_VALUES = ("user", "admin", "matchmaker")
GENDER_VALUES = ("male", "female")
SMOKING_STATUS_VALUES = ("yes", "no", "sometimes", "unknown")
DRINKING_STATUS_VALUES = ("yes", "no", "sometimes", "unknown")
PET_STATUS_VALUES = ("has_cat", "has_dog", "has_pet", "no_pet", "unknown")
ACTIVE_STATUS_VALUES = ("active", "inactive", "paused")
VERIFICATION_STATUS_VALUES = ("verified", "pending", "failed")
PREFERENCE_DIMENSION_VALUES = ("age", "height", "city", "education", "marital_status")
PREFERENCE_OPERATOR_VALUES = ("between", "in", "not_in", "gte", "lte", "eq")
PREFERENCE_PRIORITY_VALUES = ("must", "prefer", "avoid")
CONSTRAINT_TAG_TYPE_VALUES = ("block", "verify", "penalty")
CONSTRAINT_DIRECTION_VALUES = ("other_side_fact", "self_fact")
CONSTRAINT_STATUS_VALUES = ("active", "inactive", "expired")
CONSTRAINT_SCOPE_VALUES = ("block", "preference", "warning")
OBSERVER_TYPE_VALUES = ("matchmaker", "ai")
OBSERVATION_STATUS_VALUES = ("suggested", "approved", "rejected", "active")
INTERACTION_EVENT_TYPE_VALUES = ("recommend", "meet", "review", "terminate")
OUTCOME_LABEL_VALUES = ("success", "failed", "no_show")
WILLINGNESS_VALUES = ("yes", "no", "maybe", "unknown")
SNAPSHOT_STAGE_VALUES = ("rough", "final")
VERIFY_TASK_STATUS_VALUES = ("pending", "confirmed", "rejected")
VERIFY_FIELD_VALUES = (
    "age",
    "height_cm",
    "city_code",
    "education_level",
    "marital_status",
    "occupation",
    "smoking_status",
    "drinking_status",
    "pet_status",
)
AI_ENTITY_TYPE_VALUES = ("user", "memo", "event")
AI_EXTRACTION_STATUS_VALUES = ("suggested", "approved", "rejected", "failed")


def _is_sqlite() -> bool:
    return op.get_context().dialect.name == "sqlite"


def _set_sqlite_foreign_keys(enabled: bool) -> None:
    if _is_sqlite():
        op.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _sql_in(column_name: str, values: tuple[str, ...]) -> str:
    return f"{column_name} IN ({', '.join(repr(value) for value in values)})"


def _cleanup_data() -> None:
    op.execute(
        f"UPDATE user_profile SET gender = NULL WHERE gender IS NOT NULL AND NOT ({_sql_in('gender', GENDER_VALUES)})"
    )
    op.execute(
        f"UPDATE user_profile SET smoking_status = NULL WHERE smoking_status IS NOT NULL AND NOT ({_sql_in('smoking_status', SMOKING_STATUS_VALUES)})"
    )
    op.execute(
        f"UPDATE user_profile SET drinking_status = NULL WHERE drinking_status IS NOT NULL AND NOT ({_sql_in('drinking_status', DRINKING_STATUS_VALUES)})"
    )
    op.execute(
        f"UPDATE user_profile SET pet_status = NULL WHERE pet_status IS NOT NULL AND NOT ({_sql_in('pet_status', PET_STATUS_VALUES)})"
    )
    op.execute(
        f"UPDATE user_profile SET active_status = NULL WHERE active_status IS NOT NULL AND NOT ({_sql_in('active_status', ACTIVE_STATUS_VALUES)})"
    )
    op.execute(
        f"UPDATE user_profile SET verification_status = NULL WHERE verification_status IS NOT NULL AND NOT ({_sql_in('verification_status', VERIFICATION_STATUS_VALUES)})"
    )
    op.execute("UPDATE user_profile SET open_to_match = NULL WHERE open_to_match IS NOT NULL AND open_to_match NOT IN (0, 1)")
    op.execute("UPDATE user_profile SET profile_completeness = NULL WHERE profile_completeness IS NOT NULL AND (profile_completeness < 0 OR profile_completeness > 100)")

    op.execute(
        f"DELETE FROM user_preference WHERE NOT ({_sql_in('dimension', PREFERENCE_DIMENSION_VALUES)}) OR NOT ({_sql_in('operator', PREFERENCE_OPERATOR_VALUES)}) OR (priority_level IS NOT NULL AND NOT ({_sql_in('priority_level', PREFERENCE_PRIORITY_VALUES)}))"
    )

    op.execute(
        f"DELETE FROM user_constraint WHERE NOT ({_sql_in('tag_type', CONSTRAINT_TAG_TYPE_VALUES)})"
    )
    op.execute(
        f"UPDATE user_constraint SET direction = NULL WHERE direction IS NOT NULL AND NOT ({_sql_in('direction', CONSTRAINT_DIRECTION_VALUES)})"
    )
    op.execute(
        f"UPDATE user_constraint SET status = NULL WHERE status IS NOT NULL AND NOT ({_sql_in('status', CONSTRAINT_STATUS_VALUES)})"
    )
    op.execute(
        f"UPDATE user_constraint SET constraint_scope = NULL WHERE constraint_scope IS NOT NULL AND NOT ({_sql_in('constraint_scope', CONSTRAINT_SCOPE_VALUES)})"
    )

    op.execute(
        f"UPDATE user_observation_tag SET observer_type = NULL WHERE observer_type IS NOT NULL AND NOT ({_sql_in('observer_type', OBSERVER_TYPE_VALUES)})"
    )
    op.execute(
        f"UPDATE user_observation_tag SET status = NULL WHERE status IS NOT NULL AND NOT ({_sql_in('status', OBSERVATION_STATUS_VALUES)})"
    )

    op.execute(
        f"DELETE FROM interaction_event WHERE NOT ({_sql_in('event_type', INTERACTION_EVENT_TYPE_VALUES)})"
    )
    op.execute(
        f"UPDATE interaction_event SET outcome_label = NULL WHERE outcome_label IS NOT NULL AND NOT ({_sql_in('outcome_label', OUTCOME_LABEL_VALUES)})"
    )
    op.execute(
        f"UPDATE interaction_event SET willingness_a = NULL WHERE willingness_a IS NOT NULL AND NOT ({_sql_in('willingness_a', WILLINGNESS_VALUES)})"
    )
    op.execute(
        f"UPDATE interaction_event SET willingness_b = NULL WHERE willingness_b IS NOT NULL AND NOT ({_sql_in('willingness_b', WILLINGNESS_VALUES)})"
    )

    op.execute(
        f"UPDATE recommendation_snapshot SET snapshot_stage = NULL WHERE snapshot_stage IS NOT NULL AND NOT ({_sql_in('snapshot_stage', SNAPSHOT_STAGE_VALUES)})"
    )
    op.execute(
        "DELETE FROM recommendation_snapshot WHERE rec_id NOT IN ("
        "SELECT MAX(rec_id) FROM recommendation_snapshot GROUP BY requester_user_id, candidate_user_id, COALESCE(snapshot_stage, '')"
        ")"
    )

    op.execute(
        f"DELETE FROM verify_task WHERE NOT ({_sql_in('verify_field', VERIFY_FIELD_VALUES)})"
    )
    op.execute(
        f"UPDATE verify_task SET task_status = NULL WHERE task_status IS NOT NULL AND NOT ({_sql_in('task_status', VERIFY_TASK_STATUS_VALUES)})"
    )
    op.execute(
        "DELETE FROM verify_task WHERE task_id NOT IN ("
        "SELECT MAX(task_id) FROM verify_task GROUP BY requester_user_id, candidate_user_id, verify_field, COALESCE(task_status, '')"
        ")"
    )

    op.execute(
        f"DELETE FROM ai_extraction WHERE NOT ({_sql_in('entity_type', AI_ENTITY_TYPE_VALUES)})"
    )
    op.execute(
        f"UPDATE ai_extraction SET extraction_status = 'failed' WHERE extraction_status IS NOT NULL AND NOT ({_sql_in('extraction_status', AI_EXTRACTION_STATUS_VALUES)})"
    )


def upgrade() -> None:
    _set_sqlite_foreign_keys(False)
    _cleanup_data()

    op.create_table(
        "user_credential",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint(_sql_in("role", ROLE_VALUES), name="ck_user_credential_role"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profile.user_id"], ondelete="CASCADE", name="fk_user_credential_user_profile"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    with op.batch_alter_table("user_profile") as batch_op:
        batch_op.create_check_constraint("ck_user_profile_gender", _sql_in("gender", GENDER_VALUES) + " OR gender IS NULL")
        batch_op.create_check_constraint("ck_user_profile_smoking_status", _sql_in("smoking_status", SMOKING_STATUS_VALUES) + " OR smoking_status IS NULL")
        batch_op.create_check_constraint("ck_user_profile_drinking_status", _sql_in("drinking_status", DRINKING_STATUS_VALUES) + " OR drinking_status IS NULL")
        batch_op.create_check_constraint("ck_user_profile_pet_status", _sql_in("pet_status", PET_STATUS_VALUES) + " OR pet_status IS NULL")
        batch_op.create_check_constraint("ck_user_profile_active_status", _sql_in("active_status", ACTIVE_STATUS_VALUES) + " OR active_status IS NULL")
        batch_op.create_check_constraint("ck_user_profile_verification_status", _sql_in("verification_status", VERIFICATION_STATUS_VALUES) + " OR verification_status IS NULL")
        batch_op.create_check_constraint("ck_user_profile_open_to_match", "open_to_match IN (0, 1) OR open_to_match IS NULL")
        batch_op.create_check_constraint("ck_user_profile_profile_completeness", "(profile_completeness >= 0 AND profile_completeness <= 100) OR profile_completeness IS NULL")

    with op.batch_alter_table("user_preference") as batch_op:
        batch_op.create_check_constraint("ck_user_preference_dimension", _sql_in("dimension", PREFERENCE_DIMENSION_VALUES))
        batch_op.create_check_constraint("ck_user_preference_operator", _sql_in("operator", PREFERENCE_OPERATOR_VALUES))
        batch_op.create_check_constraint("ck_user_preference_priority_level", _sql_in("priority_level", PREFERENCE_PRIORITY_VALUES) + " OR priority_level IS NULL")

    with op.batch_alter_table("user_constraint") as batch_op:
        batch_op.create_check_constraint("ck_user_constraint_tag_type", _sql_in("tag_type", CONSTRAINT_TAG_TYPE_VALUES))
        batch_op.create_check_constraint("ck_user_constraint_direction", _sql_in("direction", CONSTRAINT_DIRECTION_VALUES) + " OR direction IS NULL")
        batch_op.create_check_constraint("ck_user_constraint_status", _sql_in("status", CONSTRAINT_STATUS_VALUES) + " OR status IS NULL")
        batch_op.create_check_constraint("ck_user_constraint_scope", _sql_in("constraint_scope", CONSTRAINT_SCOPE_VALUES) + " OR constraint_scope IS NULL")

    with op.batch_alter_table("user_observation_tag") as batch_op:
        batch_op.create_check_constraint("ck_user_observation_tag_observer_type", _sql_in("observer_type", OBSERVER_TYPE_VALUES) + " OR observer_type IS NULL")
        batch_op.create_check_constraint("ck_user_observation_tag_status", _sql_in("status", OBSERVATION_STATUS_VALUES) + " OR status IS NULL")

    with op.batch_alter_table("interaction_event") as batch_op:
        batch_op.create_check_constraint("ck_interaction_event_type", _sql_in("event_type", INTERACTION_EVENT_TYPE_VALUES))
        batch_op.create_check_constraint("ck_interaction_event_outcome_label", _sql_in("outcome_label", OUTCOME_LABEL_VALUES) + " OR outcome_label IS NULL")
        batch_op.create_check_constraint("ck_interaction_event_willingness_a", _sql_in("willingness_a", WILLINGNESS_VALUES) + " OR willingness_a IS NULL")
        batch_op.create_check_constraint("ck_interaction_event_willingness_b", _sql_in("willingness_b", WILLINGNESS_VALUES) + " OR willingness_b IS NULL")

    with op.batch_alter_table("recommendation_snapshot") as batch_op:
        batch_op.create_unique_constraint("uq_recommendation_snapshot_stage", ["requester_user_id", "candidate_user_id", "snapshot_stage"])
        batch_op.create_check_constraint("ck_recommendation_snapshot_stage", _sql_in("snapshot_stage", SNAPSHOT_STAGE_VALUES) + " OR snapshot_stage IS NULL")

    with op.batch_alter_table("verify_task") as batch_op:
        batch_op.create_unique_constraint("uq_verify_task_state", ["requester_user_id", "candidate_user_id", "verify_field", "task_status"])
        batch_op.create_check_constraint("ck_verify_task_status", _sql_in("task_status", VERIFY_TASK_STATUS_VALUES) + " OR task_status IS NULL")
        batch_op.create_check_constraint("ck_verify_task_field", _sql_in("verify_field", VERIFY_FIELD_VALUES))

    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.create_check_constraint("ck_ai_extraction_entity_type", _sql_in("entity_type", AI_ENTITY_TYPE_VALUES))
        batch_op.create_check_constraint("ck_ai_extraction_status", _sql_in("extraction_status", AI_EXTRACTION_STATUS_VALUES) + " OR extraction_status IS NULL")

    _set_sqlite_foreign_keys(True)


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)

    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.drop_constraint("ck_ai_extraction_status", type_="check")
        batch_op.drop_constraint("ck_ai_extraction_entity_type", type_="check")

    with op.batch_alter_table("verify_task") as batch_op:
        batch_op.drop_constraint("ck_verify_task_field", type_="check")
        batch_op.drop_constraint("ck_verify_task_status", type_="check")
        batch_op.drop_constraint("uq_verify_task_state", type_="unique")

    with op.batch_alter_table("recommendation_snapshot") as batch_op:
        batch_op.drop_constraint("ck_recommendation_snapshot_stage", type_="check")
        batch_op.drop_constraint("uq_recommendation_snapshot_stage", type_="unique")

    with op.batch_alter_table("interaction_event") as batch_op:
        batch_op.drop_constraint("ck_interaction_event_willingness_b", type_="check")
        batch_op.drop_constraint("ck_interaction_event_willingness_a", type_="check")
        batch_op.drop_constraint("ck_interaction_event_outcome_label", type_="check")
        batch_op.drop_constraint("ck_interaction_event_type", type_="check")

    with op.batch_alter_table("user_observation_tag") as batch_op:
        batch_op.drop_constraint("ck_user_observation_tag_status", type_="check")
        batch_op.drop_constraint("ck_user_observation_tag_observer_type", type_="check")

    with op.batch_alter_table("user_constraint") as batch_op:
        batch_op.drop_constraint("ck_user_constraint_scope", type_="check")
        batch_op.drop_constraint("ck_user_constraint_status", type_="check")
        batch_op.drop_constraint("ck_user_constraint_direction", type_="check")
        batch_op.drop_constraint("ck_user_constraint_tag_type", type_="check")

    with op.batch_alter_table("user_preference") as batch_op:
        batch_op.drop_constraint("ck_user_preference_priority_level", type_="check")
        batch_op.drop_constraint("ck_user_preference_operator", type_="check")
        batch_op.drop_constraint("ck_user_preference_dimension", type_="check")

    with op.batch_alter_table("user_profile") as batch_op:
        batch_op.drop_constraint("ck_user_profile_profile_completeness", type_="check")
        batch_op.drop_constraint("ck_user_profile_open_to_match", type_="check")
        batch_op.drop_constraint("ck_user_profile_verification_status", type_="check")
        batch_op.drop_constraint("ck_user_profile_active_status", type_="check")
        batch_op.drop_constraint("ck_user_profile_pet_status", type_="check")
        batch_op.drop_constraint("ck_user_profile_drinking_status", type_="check")
        batch_op.drop_constraint("ck_user_profile_smoking_status", type_="check")
        batch_op.drop_constraint("ck_user_profile_gender", type_="check")

    op.drop_table("user_credential")
    _set_sqlite_foreign_keys(True)
