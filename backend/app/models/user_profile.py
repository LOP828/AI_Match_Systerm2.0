from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import (
    ACTIVE_STATUS_VALUES,
    DRINKING_STATUS_VALUES,
    GENDER_VALUES,
    PET_STATUS_VALUES,
    SMOKING_STATUS_VALUES,
    VERIFICATION_STATUS_VALUES,
    sql_in,
)

from .base import Base


class UserProfile(Base):
    """Core user profile and matching availability state."""

    __tablename__ = "user_profile"
    __table_args__ = (
        Index("ix_user_profile_match_pool", "active_status", "open_to_match"),
        CheckConstraint(sql_in("gender", GENDER_VALUES) + " OR gender IS NULL", name="ck_user_profile_gender"),
        CheckConstraint(sql_in("smoking_status", SMOKING_STATUS_VALUES) + " OR smoking_status IS NULL", name="ck_user_profile_smoking_status"),
        CheckConstraint(sql_in("drinking_status", DRINKING_STATUS_VALUES) + " OR drinking_status IS NULL", name="ck_user_profile_drinking_status"),
        CheckConstraint(sql_in("pet_status", PET_STATUS_VALUES) + " OR pet_status IS NULL", name="ck_user_profile_pet_status"),
        CheckConstraint(sql_in("active_status", ACTIVE_STATUS_VALUES) + " OR active_status IS NULL", name="ck_user_profile_active_status"),
        CheckConstraint(sql_in("verification_status", VERIFICATION_STATUS_VALUES) + " OR verification_status IS NULL", name="ck_user_profile_verification_status"),
        CheckConstraint("open_to_match IN (0, 1) OR open_to_match IS NULL", name="ck_user_profile_open_to_match"),
        CheckConstraint("profile_completeness >= 0 AND profile_completeness <= 100 OR profile_completeness IS NULL", name="ck_user_profile_profile_completeness"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    city_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    education_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    smoking_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    drinking_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pet_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    open_to_match: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    profile_completeness: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    verification_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
