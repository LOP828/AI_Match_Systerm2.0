from typing import Any

from app.choices import (
    DRINKING_STATUS_VALUES,
    PET_STATUS_VALUES,
    SMOKING_STATUS_VALUES,
    VERIFY_FIELD_VALUES,
)

SUPPORTED_PROFILE_FIELDS = frozenset(VERIFY_FIELD_VALUES)
BLOCKABLE_PROFILE_FIELDS = frozenset({"smoking_status", "drinking_status", "pet_status"})

_NUMERIC_FIELD_RANGES: dict[str, tuple[int, int]] = {
    "age": (18, 120),
    "height_cm": (100, 250),
}

_ENUM_FIELD_VALUES: dict[str, frozenset[str]] = {
    "smoking_status": frozenset(SMOKING_STATUS_VALUES),
    "drinking_status": frozenset(DRINKING_STATUS_VALUES),
    "pet_status": frozenset(PET_STATUS_VALUES),
}

_TEXT_FIELD_LIMITS: dict[str, int] = {
    "city_code": 32,
    "education_level": 32,
    "marital_status": 32,
    "occupation": 64,
}


def is_supported_profile_field(field: str | None) -> bool:
    return bool(field) and field in SUPPORTED_PROFILE_FIELDS


def normalize_profile_field_value(field: str, raw_value: Any) -> int | str:
    if not is_supported_profile_field(field):
        raise ValueError(f"Unsupported profile field: {field}")

    if field in _NUMERIC_FIELD_RANGES:
        lower, upper = _NUMERIC_FIELD_RANGES[field]
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Field '{field}' requires an integer value") from exc
        if value < lower or value > upper:
            raise ValueError(f"Field '{field}' must be between {lower} and {upper}")
        return value

    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(f"Field '{field}' cannot be empty")

    if field in _ENUM_FIELD_VALUES:
        normalized = value.lower()
        if normalized not in _ENUM_FIELD_VALUES[field]:
            allowed = ", ".join(sorted(_ENUM_FIELD_VALUES[field]))
            raise ValueError(f"Field '{field}' must be one of: {allowed}")
        return normalized

    max_length = _TEXT_FIELD_LIMITS[field]
    if len(value) > max_length:
        raise ValueError(f"Field '{field}' exceeds max length {max_length}")
    return value
