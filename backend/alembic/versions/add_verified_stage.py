"""add verified to snapshot_stage enum

Revision ID: add_verified_stage
Revises: harden_constraints_auth
Create Date: 2026-03-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "add_verified_stage"
down_revision: Union[str, None] = "harden_constraints_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_VALUES = ("rough", "final")
NEW_VALUES = ("rough", "verified", "final")


def _sql_in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    with op.batch_alter_table("recommendation_snapshot") as batch_op:
        batch_op.drop_constraint("ck_recommendation_snapshot_stage", type_="check")
        batch_op.create_check_constraint(
            "ck_recommendation_snapshot_stage",
            _sql_in("snapshot_stage", NEW_VALUES) + " OR snapshot_stage IS NULL",
        )


def downgrade() -> None:
    op.execute(
        "UPDATE recommendation_snapshot SET snapshot_stage = 'rough' "
        "WHERE snapshot_stage = 'verified'"
    )
    with op.batch_alter_table("recommendation_snapshot") as batch_op:
        batch_op.drop_constraint("ck_recommendation_snapshot_stage", type_="check")
        batch_op.create_check_constraint(
            "ck_recommendation_snapshot_stage",
            _sql_in("snapshot_stage", OLD_VALUES) + " OR snapshot_stage IS NULL",
        )
