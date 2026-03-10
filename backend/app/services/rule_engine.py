"""Hard-rule filtering and constraint evaluation."""

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import UserConstraint, UserPreference, UserProfile


def _parse_preference_value(pref: UserPreference) -> dict[str, Any] | None:
    if not pref.value_json:
        return None
    return pref.value_json if isinstance(pref.value_json, dict) else None


def filter_by_hard_rules(
    db: Session,
    requester_user_id: int,
    filters: dict[str, Any] | None = None,
) -> list[int]:
    """
    Stage 1+2 filtering: serviceability and hard preference constraints.
    Returns candidate user_ids that pass hard rules.
    """
    filters = filters or {}
    requester = db.query(UserProfile.user_id).filter(UserProfile.user_id == requester_user_id).first()
    if not requester:
        return []

    q = db.query(UserProfile.user_id).filter(
        UserProfile.user_id != requester_user_id,
        or_(
            UserProfile.active_status == "active",
            UserProfile.active_status.is_(None),
        ),
        or_(
            UserProfile.open_to_match == 1,
            UserProfile.open_to_match.is_(None),
        ),
    )

    prefs = db.query(UserPreference).filter(
        UserPreference.user_id == requester_user_id,
        UserPreference.priority_level == "must",
    ).all()

    for pref in prefs:
        val = _parse_preference_value(pref)
        if not val:
            continue
        dim = pref.dimension
        op = pref.operator

        if dim == "age" and op == "between":
            age_min = val.get("min")
            age_max = val.get("max")
            if age_min is not None:
                q = q.filter(UserProfile.age >= age_min)
            if age_max is not None:
                q = q.filter(UserProfile.age <= age_max)
        elif dim == "height" and op == "between":
            h_min = val.get("min")
            h_max = val.get("max")
            if h_min is not None:
                q = q.filter(UserProfile.height_cm >= h_min)
            if h_max is not None:
                q = q.filter(UserProfile.height_cm <= h_max)
        elif dim == "city" and op == "in":
            cities = val.get("values") or val.get("cities") or []
            if cities:
                q = q.filter(UserProfile.city_code.in_(cities))
        elif dim == "education" and op == "in":
            levels = val.get("values") or val.get("education_levels") or []
            if levels:
                q = q.filter(UserProfile.education_level.in_(levels))
        elif dim == "marital_status" and op == "in":
            statuses = val.get("values") or val.get("marital_statuses") or []
            if statuses:
                q = q.filter(UserProfile.marital_status.in_(statuses))

    if filters.get("ageMin") is not None:
        q = q.filter(UserProfile.age >= filters["ageMin"])
    if filters.get("ageMax") is not None:
        q = q.filter(UserProfile.age <= filters["ageMax"])
    if filters.get("heightMin") is not None:
        q = q.filter(UserProfile.height_cm >= filters["heightMin"])
    if filters.get("heightMax") is not None:
        q = q.filter(UserProfile.height_cm <= filters["heightMax"])
    if filters.get("cities"):
        q = q.filter(UserProfile.city_code.in_(filters["cities"]))
    if filters.get("educationLevels"):
        q = q.filter(UserProfile.education_level.in_(filters["educationLevels"]))
    if filters.get("maritalStatuses"):
        q = q.filter(UserProfile.marital_status.in_(filters["maritalStatuses"]))

    return [r[0] for r in q.all()]


def get_active_constraints(
    db: Session,
    requester_user_id: int,
) -> tuple[list[UserConstraint], list[UserConstraint], list[UserConstraint]]:
    """Return (all_active, block_active, verify_active) constraints for requester."""
    constraints = db.query(UserConstraint).filter(
        UserConstraint.user_id == requester_user_id,
        UserConstraint.status == "active",
    ).all()
    block_constraints = [c for c in constraints if c.tag_type == "block"]
    verify_constraints = [c for c in constraints if c.tag_type == "verify"]
    return constraints, block_constraints, verify_constraints


def _is_block_hit(constraint: UserConstraint, value: Any) -> bool:
    if value is None:
        return False

    tag_code = (constraint.tag_code or "").lower()
    value_text = str(value).lower()

    if "cat" in tag_code and value_text in ("has_cat", "has_pet"):
        return True
    if "smok" in tag_code and value_text in ("yes", "sometimes"):
        return True
    if "dog" in tag_code and value_text in ("has_dog", "has_pet"):
        return True
    if "drink" in tag_code and value_text in ("yes", "sometimes"):
        return True
    return False


def evaluate_block_constraints(
    candidate: UserProfile,
    block_constraints: list[UserConstraint],
) -> tuple[bool, list[UserConstraint]]:
    """Evaluate whether candidate is blocked by active block constraints."""
    blocked_constraints: list[UserConstraint] = []
    for constraint in block_constraints:
        field = constraint.applies_to_field
        if not field:
            continue
        value = getattr(candidate, field, None)
        if _is_block_hit(constraint, value):
            blocked_constraints.append(constraint)
    return len(blocked_constraints) > 0, blocked_constraints


def collect_unknown_constraints(
    candidate: UserProfile,
    verify_constraints: list[UserConstraint],
) -> list[UserConstraint]:
    """Return verify constraints whose target field value is unknown on candidate."""
    unknown: list[UserConstraint] = []
    for constraint in verify_constraints:
        field = constraint.applies_to_field
        if not field:
            unknown.append(constraint)
            continue
        value = getattr(candidate, field, None)
        if value is None or (isinstance(value, str) and value.lower() == "unknown"):
            unknown.append(constraint)
    return unknown


def check_known_constraints(
    db: Session,
    requester_user_id: int,
    candidate_user_id: int,
) -> tuple[bool, list[UserConstraint]]:
    """Compatibility wrapper for evaluating block constraints via DB lookups."""
    _, block_constraints, _ = get_active_constraints(db, requester_user_id)
    candidate = db.query(UserProfile).filter(UserProfile.user_id == candidate_user_id).first()
    if not candidate:
        return True, []
    return evaluate_block_constraints(candidate, block_constraints)


def get_unknown_constraints(
    db: Session,
    requester_user_id: int,
    candidate_user_id: int,
) -> list[UserConstraint]:
    """Compatibility wrapper for collecting unknown verify constraints via DB lookups."""
    _, _, verify_constraints = get_active_constraints(db, requester_user_id)
    candidate = db.query(UserProfile).filter(UserProfile.user_id == candidate_user_id).first()
    if not candidate:
        return []
    return collect_unknown_constraints(candidate, verify_constraints)
