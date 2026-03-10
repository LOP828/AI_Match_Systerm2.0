from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import VERIFY_FIELD_VALUES, VERIFY_TASK_STATUS_VALUES, sql_in

from .base import Base


class VerifyTask(Base):
    """Pending verification tasks created from rough ranking."""

    __tablename__ = "verify_task"
    __table_args__ = (
        Index("ix_verify_task_feed", "requester_user_id", "task_status", "created_at"),
        UniqueConstraint("requester_user_id", "candidate_user_id", "verify_field", "task_status", name="uq_verify_task_state"),
        CheckConstraint(sql_in("task_status", VERIFY_TASK_STATUS_VALUES) + " OR task_status IS NULL", name="ck_verify_task_status"),
        CheckConstraint(sql_in("verify_field", VERIFY_FIELD_VALUES), name="ck_verify_task_field"),
    )

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    verify_field: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rough_rank_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    task_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
