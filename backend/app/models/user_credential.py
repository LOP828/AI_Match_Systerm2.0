from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import ROLE_VALUES, sql_in

from .base import Base


class UserCredential(Base):
    """Local password credential and role assignment for one user."""

    __tablename__ = "user_credential"
    __table_args__ = (
        CheckConstraint(sql_in("role", ROLE_VALUES), name="ck_user_credential_role"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="user")
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
