from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import (
    CONSTRAINT_DIRECTION_VALUES,
    CONSTRAINT_SCOPE_VALUES,
    CONSTRAINT_STATUS_VALUES,
    CONSTRAINT_TAG_TYPE_VALUES,
    sql_in,
)

from .base import Base


class UserConstraint(Base):
    """Constraint tags: block / verify / penalty."""

    __tablename__ = "user_constraint"
    __table_args__ = (
        Index("ix_user_constraint_lookup", "user_id", "tag_type", "status"),
        CheckConstraint(sql_in("tag_type", CONSTRAINT_TAG_TYPE_VALUES), name="ck_user_constraint_tag_type"),
        CheckConstraint(sql_in("direction", CONSTRAINT_DIRECTION_VALUES) + " OR direction IS NULL", name="ck_user_constraint_direction"),
        CheckConstraint(sql_in("status", CONSTRAINT_STATUS_VALUES) + " OR status IS NULL", name="ck_user_constraint_status"),
        CheckConstraint(sql_in("constraint_scope", CONSTRAINT_SCOPE_VALUES) + " OR constraint_scope IS NULL", name="ck_user_constraint_scope"),
    )

    constraint_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_code: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_type: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_human_confirmed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    constraint_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applies_to_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirm_required: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
