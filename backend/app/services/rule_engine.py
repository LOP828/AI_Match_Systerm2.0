"""Hard-rule filtering and constraint evaluation."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import UserConstraint, UserPreference, UserProfile
from app.profile_fields import is_supported_profile_field


def _parse_preference_value(pref: UserPreference) -> dict[str, Any] | None:
    if not pref.value_json:
        return None
    return pref.value_json if isinstance(pref.value_json, dict) else None


def _extract_scalar_value(payload: dict[str, Any]) -> Any:
    if "value" in payload:
        return payload["value"]
    if "target" in payload:
        return payload["target"]
    return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_list_values(pref: UserPreference, payload: dict[str, Any]) -> list[Any]:
    if isinstance(payload.get("values"), list):
        return payload["values"]

    alias_keys = {
        "city": "cities",
        "education": "education_levels",
        "marital_status": "marital_statuses",
    }
    alias_key = alias_keys.get(pref.dimension)
    if alias_key and isinstance(payload.get(alias_key), list):
        return payload[alias_key]

    return []


def _apply_numeric_preference_filter(query, column, operator: str, payload: dict[str, Any]):
    if operator == "between":
        lower = _to_int(payload.get("min"))
        upper = _to_int(payload.get("max"))
        if lower is not None:
            query = query.filter(column >= lower)
        if upper is not None:
            query = query.filter(column <= upper)
        return query

    if operator == "gte":
        target = _to_int(_extract_scalar_value(payload))
        return query.filter(column >= target) if target is not None else query

    if operator == "lte":
        target = _to_int(_extract_scalar_value(payload))
        return query.filter(column <= target) if target is not None else query

    if operator == "eq":
        target = _to_int(_extract_scalar_value(payload))
        return query.filter(column == target) if target is not None else query

    values = payload.get("values")
    if isinstance(values, list):
        normalized_values = [item for item in (_to_int(value) for value in values) if item is not None]
    else:
        normalized_values = []
    if normalized_values:
        if operator == "in":
            return query.filter(column.in_(normalized_values))
        if operator == "not_in":
            return query.filter(~column.in_(normalized_values))
    return query


def _apply_text_preference_filter(query, column, pref: UserPreference, payload: dict[str, Any]):
    if pref.operator == "eq":
        target = _extract_scalar_value(payload)
        return query.filter(column == target) if target else query

    values = _extract_list_values(pref, payload)
    if values:
        if pref.operator == "in":
            return query.filter(column.in_(values))
        if pref.operator == "not_in":
            return query.filter(~column.in_(values))
    return query


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
        UserProfile.active_status == "active",
        UserProfile.open_to_match == 1,
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
        if dim == "age":
            q = _apply_numeric_preference_filter(q, UserProfile.age, pref.operator, val)
        elif dim == "height":
            q = _apply_numeric_preference_filter(q, UserProfile.height_cm, pref.operator, val)
        elif dim == "city":
            q = _apply_text_preference_filter(q, UserProfile.city_code, pref, val)
        elif dim == "education":
            q = _apply_text_preference_filter(q, UserProfile.education_level, pref, val)
        elif dim == "marital_status":
            q = _apply_text_preference_filter(q, UserProfile.marital_status, pref, val)

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


# Maps each profile field to the set of values that trigger a block constraint.
# A block constraint on a field means: "exclude candidates whose field value is
# in this set."  The tag_code on the constraint names the *reason* (e.g.
# "no_smoker"), not the blocked value itself, so we derive the trigger set from
# the field name rather than from fragile tag_code keyword matching.
_FIELD_BLOCK_VALUES: dict[str, frozenset[str]] = {
    "smoking_status": frozenset({"yes", "sometimes"}),
    "drinking_status": frozenset({"yes", "sometimes"}),
    "pet_status": frozenset({"has_cat", "has_dog", "has_pet"}),
}


def _is_block_hit(constraint: UserConstraint, value: Any) -> bool:
    if value is None:
        return False
    field = constraint.applies_to_field or ""
    blocked_values = _FIELD_BLOCK_VALUES.get(field)
    if blocked_values is None:
        return False
    return str(value).strip().lower() in blocked_values


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
        if not is_supported_profile_field(field):
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
