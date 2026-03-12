"""多头评分与粗排/精排"""

from decimal import Decimal, InvalidOperation
from typing import Any

from app.models import UserPreference, UserProfile

SOFT_PREFERENCE_FIELD_MAP = {
    "age": "age",
    "height": "height_cm",
    "city": "city_code",
    "education": "education_level",
    "marital_status": "marital_status",
}

RANGE_STYLE_OPERATORS = {"between", "gte", "lte"}
NUMERIC_PREFERENCE_DIMENSIONS = {"age", "height"}


def _clamp_score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, InvalidOperation, ValueError):
        return None


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


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


def _extract_scalar_value(payload: dict[str, Any]) -> Any:
    if "value" in payload:
        return payload["value"]
    if "target" in payload:
        return payload["target"]
    return None


def _matches_soft_preference(pref: UserPreference, candidate_value: Any) -> bool | None:
    if candidate_value is None:
        return None
    if isinstance(candidate_value, str) and candidate_value.strip().lower() == "unknown":
        return None

    payload = pref.value_json if isinstance(pref.value_json, dict) else {}
    operator = pref.operator

    if operator == "between":
        candidate_number = _to_decimal(candidate_value)
        if candidate_number is None:
            return None
        lower = _to_decimal(payload.get("min"))
        upper = _to_decimal(payload.get("max"))
        if lower is None and upper is None:
            return False
        return (lower is None or candidate_number >= lower) and (upper is None or candidate_number <= upper)

    if operator in {"gte", "lte"}:
        candidate_number = _to_decimal(candidate_value)
        target = _to_decimal(_extract_scalar_value(payload))
        if candidate_number is None:
            return None
        if target is None:
            return False
        return candidate_number >= target if operator == "gte" else candidate_number <= target

    if operator in {"in", "not_in"}:
        values = _extract_list_values(pref, payload)
        if not values:
            return False
        normalized_values = {_normalize_text(value) for value in values}
        contains = _normalize_text(candidate_value) in normalized_values
        return contains if operator == "in" else not contains

    if operator == "eq":
        target = _extract_scalar_value(payload)
        if target is None:
            return False
        if pref.dimension in NUMERIC_PREFERENCE_DIMENSIONS:
            candidate_number = _to_decimal(candidate_value)
            target_number = _to_decimal(target)
            if candidate_number is None:
                return None
            if target_number is None:
                return False
            return candidate_number == target_number
        return _normalize_text(candidate_value) == _normalize_text(target)

    return False


def _soft_preference_weight(pref: UserPreference) -> Decimal:
    if pref.operator in RANGE_STYLE_OPERATORS:
        return Decimal("8")
    return Decimal("12")


def score_soft_preferences(
    candidate: UserProfile,
    requester_preferences: list[UserPreference] | None,
) -> dict[str, Any]:
    """Score saved prefer/avoid rules without filtering the candidate out.

    `must` preferences are still enforced upstream by the rule engine. This step
    only adjusts ranking for soft preferences that should influence ordering.
    """
    result: dict[str, Any] = {
        "adjustment": Decimal("0"),
        "applied": [],
        "unmet": [],
        "unknown": [],
    }
    if not requester_preferences:
        return result

    for pref in requester_preferences:
        if pref.priority_level not in {"prefer", "avoid"}:
            continue

        candidate_field = SOFT_PREFERENCE_FIELD_MAP.get(pref.dimension)
        if not candidate_field:
            continue

        candidate_value = getattr(candidate, candidate_field, None)
        outcome = _matches_soft_preference(pref, candidate_value)
        summary = {
            "dimension": pref.dimension,
            "operator": pref.operator,
            "priority": pref.priority_level,
            "candidateValue": candidate_value,
            "valueJson": pref.value_json,
        }

        if outcome is None:
            result["unknown"].append(summary)
            continue

        if outcome:
            delta = _soft_preference_weight(pref)
            if pref.priority_level == "avoid":
                delta = -delta
            result["adjustment"] += delta
            result["applied"].append({
                **summary,
                "delta": float(delta),
            })
            continue

        result["unmet"].append(summary)

    return result


def calculate_multi_scores(
    requester: UserProfile,
    candidate: UserProfile,
    unknown_constraint_count: int = 0,
    preference_adjustment: Decimal | None = None,
) -> dict[str, Decimal]:
    """
    计算多头评分：安全度、聊天顺畅度、二次见面概率、冲突风险
    返回值 0-100

    unknown_constraint_count: 该候选人尚未确认的 verify 约束数（per-candidate）
    """
    safety = Decimal("85")  # 默认
    chat = Decimal("75")
    second_date = Decimal("70")
    conflict = Decimal("20")  # 冲突风险，越低越好

    # 安全度：按该候选人实际未知约束数扣分，每项 -5
    if unknown_constraint_count > 0:
        safety = safety - Decimal(unknown_constraint_count) * 5
    safety = _clamp_score(safety)

    # 聊天顺畅度：年龄差、城市、学历匹配
    if requester.age and candidate.age:
        age_diff = abs(requester.age - candidate.age)
        if age_diff <= 3:
            chat += Decimal("10")
        elif age_diff <= 5:
            chat += Decimal("5")
        elif age_diff > 10:
            chat -= Decimal("10")
    if requester.city_code and candidate.city_code and requester.city_code == candidate.city_code:
        chat += Decimal("8")
    if requester.education_level and candidate.education_level:
        edu_order = ["high_school", "bachelor", "master", "phd"]
        try:
            r_idx = edu_order.index(requester.education_level)
            c_idx = edu_order.index(candidate.education_level)
            if abs(r_idx - c_idx) <= 1:
                chat += Decimal("5")
        except ValueError:
            pass

    # Soft prefer/avoid rules are applied as a ranking adjustment rather than a
    # filter so the existing API can keep exposing the same score structure.
    if preference_adjustment is not None:
        chat += preference_adjustment
    chat = _clamp_score(chat)

    # 二次见面概率：综合
    second_date = (safety + chat) / 2
    second_date = _clamp_score(second_date)

    # 冲突风险：生活方式差异
    if requester.smoking_status and candidate.smoking_status:
        if requester.smoking_status != candidate.smoking_status:
            conflict += Decimal("15")
    if requester.pet_status and candidate.pet_status:
        if "has" in (requester.pet_status or "") and "no" in (candidate.pet_status or ""):
            conflict += Decimal("10")
    conflict = _clamp_score(conflict)

    return {
        "safetyScore": safety,
        "chatScore": chat,
        "secondDateScore": second_date,
        "conflictRiskScore": conflict,
    }
