"""add extraction_type column to ai_extraction

Revision ID: add_extraction_type
Revises: add_verified_stage
Create Date: 2026-03-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "add_extraction_type"
down_revision: Union[str, None] = "add_verified_stage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXTRACTION_TYPE_VALUES = ("observation", "risk")


def _sql_in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.add_column(sa.Column("extraction_type", sa.String(16), nullable=True))
        batch_op.create_check_constraint(
            "ck_ai_extraction_type",
            _sql_in("extraction_type", EXTRACTION_TYPE_VALUES) + " OR extraction_type IS NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_extraction") as batch_op:
        batch_op.drop_constraint("ck_ai_extraction_type", type_="check")
        batch_op.drop_column("extraction_type")
