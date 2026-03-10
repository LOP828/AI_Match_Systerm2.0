from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import OBSERVATION_STATUS_VALUES, OBSERVER_TYPE_VALUES, sql_in

from .base import Base


class UserObservationTag(Base):
    """Observation tags from human or AI review."""

    __tablename__ = "user_observation_tag"
    __table_args__ = (
        Index("ix_user_observation_tag_user", "user_id", "status"),
        CheckConstraint(sql_in("observer_type", OBSERVER_TYPE_VALUES) + " OR observer_type IS NULL", name="ck_user_observation_tag_observer_type"),
        CheckConstraint(sql_in("status", OBSERVATION_STATUS_VALUES) + " OR status IS NULL", name="ck_user_observation_tag_status"),
    )

    tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_code: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    observer_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
