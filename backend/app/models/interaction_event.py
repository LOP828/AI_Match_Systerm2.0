from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import INTERACTION_EVENT_TYPE_VALUES, OUTCOME_LABEL_VALUES, WILLINGNESS_VALUES, sql_in

from .base import Base


class InteractionEvent(Base):
    """Interaction events between two users."""

    __tablename__ = "interaction_event"
    __table_args__ = (
        Index("ix_interaction_event_pair_ab", "user_a_id", "user_b_id", "event_time"),
        Index("ix_interaction_event_pair_ba", "user_b_id", "user_a_id", "event_time"),
        CheckConstraint(sql_in("event_type", INTERACTION_EVENT_TYPE_VALUES), name="ck_interaction_event_type"),
        CheckConstraint(sql_in("outcome_label", OUTCOME_LABEL_VALUES) + " OR outcome_label IS NULL", name="ck_interaction_event_outcome_label"),
        CheckConstraint(sql_in("willingness_a", WILLINGNESS_VALUES) + " OR willingness_a IS NULL", name="ck_interaction_event_willingness_a"),
        CheckConstraint(sql_in("willingness_b", WILLINGNESS_VALUES) + " OR willingness_b IS NULL", name="ck_interaction_event_willingness_b"),
    )

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_a_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_b_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    outcome_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    willingness_a: Mapped[str | None] = mapped_column(String(32), nullable=True)
    willingness_b: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issue_tags_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    conversation_smoothness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    appearance_acceptance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    values_alignment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reject_reason_primary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reject_reason_secondary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    memo_ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
