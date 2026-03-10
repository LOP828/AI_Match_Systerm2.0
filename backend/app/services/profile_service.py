from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    UserConstraint,
    UserObservationTag,
    UserPreference,
    UserProfile,
)


def _ensure_user_exists(db: Session, user_id: int) -> None:
    exists = db.query(UserProfile.user_id).filter(UserProfile.user_id == user_id).first()
    if not exists:
        raise ValueError(f"User {user_id} does not exist")


def get_user_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def upsert_user_profile(db: Session, user_id: int, data: dict[str, Any]) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile:
        for k, v in data.items():
            if hasattr(profile, k):
                setattr(profile, k, v)
    else:
        profile = UserProfile(user_id=user_id, **{k: v for k, v in data.items() if hasattr(UserProfile, k)})
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_user_preferences(db: Session, user_id: int) -> list[UserPreference]:
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).all()


def add_user_preference(db: Session, user_id: int, data: dict[str, Any]) -> UserPreference:
    _ensure_user_exists(db, user_id)

    pref = UserPreference(user_id=user_id, **data)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def get_user_constraints(db: Session, user_id: int, status: str = "active") -> list[UserConstraint]:
    return db.query(UserConstraint).filter(
        UserConstraint.user_id == user_id,
        UserConstraint.status == status,
    ).all()


def add_user_constraint(db: Session, user_id: int, data: dict[str, Any]) -> UserConstraint:
    _ensure_user_exists(db, user_id)

    allowed = {"tag_code", "tag_type", "applies_to_field", "source_type", "direction", "confidence"}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    if "confidence" in kwargs and kwargs["confidence"] is not None:
        kwargs["confidence"] = Decimal(str(kwargs["confidence"]))
    constraint = UserConstraint(
        user_id=user_id,
        status="active",
        constraint_scope="block" if kwargs.get("tag_type") == "block" else "warning",
        **kwargs,
    )
    db.add(constraint)
    db.commit()
    db.refresh(constraint)
    return constraint


def get_user_observation_tags(db: Session, user_id: int) -> list[UserObservationTag]:
    return db.query(UserObservationTag).filter(UserObservationTag.user_id == user_id).all()


def add_user_observation_tag(db: Session, user_id: int, data: dict[str, Any]) -> UserObservationTag:
    _ensure_user_exists(db, user_id)

    allowed = {"tag_code", "tag_value", "confidence", "observer_type"}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    conf = kwargs.pop("confidence", 80)
    tag = UserObservationTag(
        user_id=user_id,
        status="active",
        confidence=Decimal(str(conf)),
        **kwargs,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
