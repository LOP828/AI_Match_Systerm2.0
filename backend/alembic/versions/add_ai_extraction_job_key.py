"""add ai extraction job key for trigger dedupe

Revision ID: add_ai_extraction_job_key
Revises: add_feedback_fields
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "add_ai_extraction_job_key"
down_revision: Union[str, None] = "add_feedback_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.add_column(sa.Column("job_key", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint("uq_ai_extraction_job_key", ["job_key"])


def downgrade() -> None:
    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.drop_constraint("uq_ai_extraction_job_key", type_="unique")
        batch_op.drop_column("job_key")
