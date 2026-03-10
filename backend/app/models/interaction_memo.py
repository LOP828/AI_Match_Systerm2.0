from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class InteractionMemo(Base):
    """Raw memo text linked to interaction events."""

    __tablename__ = "interaction_memo"
    __table_args__ = (
        Index("ix_interaction_memo_event", "related_event_id"),
    )

    memo_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    related_event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interaction_event.event_id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
