"""add structured feedback fields to interaction_event

Revision ID: add_feedback_fields
Revises: add_extraction_type
Create Date: 2026-03-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "add_feedback_fields"
down_revision: Union[str, None] = "add_extraction_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("interaction_event") as batch_op:
        batch_op.add_column(sa.Column("conversation_smoothness", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("appearance_acceptance", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("values_alignment", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reject_reason_primary", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("reject_reason_secondary", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("interaction_event") as batch_op:
        batch_op.drop_column("reject_reason_secondary")
        batch_op.drop_column("reject_reason_primary")
        batch_op.drop_column("values_alignment")
        batch_op.drop_column("appearance_acceptance")
        batch_op.drop_column("conversation_smoothness")
