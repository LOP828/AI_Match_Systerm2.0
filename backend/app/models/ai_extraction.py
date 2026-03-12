from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import AI_ENTITY_TYPE_VALUES, AI_EXTRACTION_STATUS_VALUES, EXTRACTION_TYPE_VALUES, sql_in

from .base import Base


class AiExtraction(Base):
    """AI extraction suggestions and evidence records."""

    __tablename__ = "ai_extraction"
    __table_args__ = (
        Index("ix_ai_extraction_lookup", "entity_type", "entity_id", "extraction_status"),
        UniqueConstraint("job_key", name="uq_ai_extraction_job_key"),
        CheckConstraint(sql_in("entity_type", AI_ENTITY_TYPE_VALUES), name="ck_ai_extraction_entity_type"),
        CheckConstraint(sql_in("extraction_status", AI_EXTRACTION_STATUS_VALUES) + " OR extraction_status IS NULL", name="ck_ai_extraction_status"),
        CheckConstraint(sql_in("extraction_type", EXTRACTION_TYPE_VALUES) + " OR extraction_type IS NULL", name="ck_ai_extraction_type"),
    )

    extraction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extracted_label: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    job_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
