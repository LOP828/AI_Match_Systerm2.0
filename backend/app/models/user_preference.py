from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import (
    PREFERENCE_DIMENSION_VALUES,
    PREFERENCE_OPERATOR_VALUES,
    PREFERENCE_PRIORITY_VALUES,
    sql_in,
)

from .base import Base


class UserPreference(Base):
    """User preference rules used by hard filtering and ranking."""

    __tablename__ = "user_preference"
    __table_args__ = (
        Index("ix_user_preference_lookup", "user_id", "priority_level"),
        CheckConstraint(sql_in("dimension", PREFERENCE_DIMENSION_VALUES), name="ck_user_preference_dimension"),
        CheckConstraint(sql_in("operator", PREFERENCE_OPERATOR_VALUES), name="ck_user_preference_operator"),
        CheckConstraint(sql_in("priority_level", PREFERENCE_PRIORITY_VALUES) + " OR priority_level IS NULL", name="ck_user_preference_priority_level"),
    )

    preference_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False)
    value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    priority_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed_by_matchmaker: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
