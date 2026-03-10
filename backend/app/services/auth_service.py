import hashlib
import hmac
import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.choices import ROLE_VALUES
from app.models import UserCredential, UserProfile

PBKDF2_ITERATIONS = 120_000


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    role: str


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    ).hex()


def _normalize_role(role: str) -> str:
    normalized = (role or "user").strip().lower()
    if normalized not in ROLE_VALUES:
        raise ValueError(f"Invalid role: {role}")
    return normalized


def build_password_credential(password: str) -> tuple[str, str]:
    salt = os.urandom(16)
    return salt.hex(), _hash_password(password, salt)


def verify_password(password: str, salt_hex: str, password_hash: str) -> bool:
    computed = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(computed, password_hash)


def upsert_password_credential(db: Session, user_id: int, password: str, role: str) -> UserCredential:
    user = db.query(UserProfile.user_id).filter(UserProfile.user_id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} does not exist")

    normalized_role = _normalize_role(role)
    salt_hex, password_hash = build_password_credential(password)
    credential = db.query(UserCredential).filter(UserCredential.user_id == user_id).first()
    if credential is None:
        credential = UserCredential(
            user_id=user_id,
            role=normalized_role,
            password_hash=password_hash,
            password_salt=salt_hex,
        )
        db.add(credential)
    else:
        credential.role = normalized_role
        credential.password_hash = password_hash
        credential.password_salt = salt_hex

    db.commit()
    db.refresh(credential)
    return credential


def authenticate_with_password(db: Session, user_id: int, password: str) -> AuthenticatedUser | None:
    credential = db.query(UserCredential).filter(UserCredential.user_id == user_id).first()
    if credential is None:
        return None
    if not verify_password(password, credential.password_salt, credential.password_hash):
        return None
    return AuthenticatedUser(user_id=credential.user_id, role=credential.role)
