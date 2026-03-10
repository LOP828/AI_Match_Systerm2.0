from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import SNAPSHOT_STAGE_VALUES, sql_in

from .base import Base


class RecommendationSnapshot(Base):
    """Stored recommendation snapshots for requester feeds."""

    __tablename__ = "recommendation_snapshot"
    __table_args__ = (
        Index("ix_recommendation_snapshot_feed", "requester_user_id", "snapshot_stage", "created_at"),
        UniqueConstraint("requester_user_id", "candidate_user_id", "snapshot_stage", name="uq_recommendation_snapshot_stage"),
        CheckConstraint(sql_in("snapshot_stage", SNAPSHOT_STAGE_VALUES) + " OR snapshot_stage IS NULL", name="ck_recommendation_snapshot_stage"),
    )

    rec_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    safety_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    chat_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    second_date_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    conflict_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    verify_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_rank_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    explanation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    snapshot_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    verify_pending_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verify_task_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rank_change_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
