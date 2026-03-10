from typing import Literal, TypeAlias, get_args


RoleType: TypeAlias = Literal["user", "admin", "matchmaker"]
GenderType: TypeAlias = Literal["male", "female"]
SmokingStatusType: TypeAlias = Literal["yes", "no", "sometimes", "unknown"]
DrinkingStatusType: TypeAlias = Literal["yes", "no", "sometimes", "unknown"]
PetStatusType: TypeAlias = Literal["has_cat", "has_dog", "has_pet", "no_pet", "unknown"]
ActiveStatusType: TypeAlias = Literal["active", "inactive", "paused"]
VerificationStatusType: TypeAlias = Literal["verified", "pending", "failed"]
PreferenceDimensionType: TypeAlias = Literal["age", "height", "city", "education", "marital_status"]
PreferenceOperatorType: TypeAlias = Literal["between", "in", "not_in", "gte", "lte", "eq"]
PreferencePriorityType: TypeAlias = Literal["must", "prefer", "avoid"]
ConstraintTagType: TypeAlias = Literal["block", "verify", "penalty"]
ConstraintDirectionType: TypeAlias = Literal["other_side_fact", "self_fact"]
ConstraintStatusType: TypeAlias = Literal["active", "inactive", "expired"]
ConstraintScopeType: TypeAlias = Literal["block", "preference", "warning"]
ObserverType: TypeAlias = Literal["matchmaker", "ai"]
ObservationStatusType: TypeAlias = Literal["suggested", "approved", "rejected", "active"]
InteractionEventType: TypeAlias = Literal["recommend", "meet", "review", "terminate"]
OutcomeLabelType: TypeAlias = Literal["success", "failed", "no_show"]
WillingnessType: TypeAlias = Literal["yes", "no", "maybe", "unknown"]
SnapshotStageType: TypeAlias = Literal["rough", "final"]
VerifyTaskStatusType: TypeAlias = Literal["pending", "confirmed", "rejected"]
AiEntityType: TypeAlias = Literal["user", "memo", "event"]
AiExtractionStatusType: TypeAlias = Literal["suggested", "approved", "rejected", "failed"]

ROLE_VALUES = get_args(RoleType)
GENDER_VALUES = get_args(GenderType)
SMOKING_STATUS_VALUES = get_args(SmokingStatusType)
DRINKING_STATUS_VALUES = get_args(DrinkingStatusType)
PET_STATUS_VALUES = get_args(PetStatusType)
ACTIVE_STATUS_VALUES = get_args(ActiveStatusType)
VERIFICATION_STATUS_VALUES = get_args(VerificationStatusType)
PREFERENCE_DIMENSION_VALUES = get_args(PreferenceDimensionType)
PREFERENCE_OPERATOR_VALUES = get_args(PreferenceOperatorType)
PREFERENCE_PRIORITY_VALUES = get_args(PreferencePriorityType)
CONSTRAINT_TAG_TYPE_VALUES = get_args(ConstraintTagType)
CONSTRAINT_DIRECTION_VALUES = get_args(ConstraintDirectionType)
CONSTRAINT_STATUS_VALUES = get_args(ConstraintStatusType)
CONSTRAINT_SCOPE_VALUES = get_args(ConstraintScopeType)
OBSERVER_TYPE_VALUES = get_args(ObserverType)
OBSERVATION_STATUS_VALUES = get_args(ObservationStatusType)
INTERACTION_EVENT_TYPE_VALUES = get_args(InteractionEventType)
OUTCOME_LABEL_VALUES = get_args(OutcomeLabelType)
WILLINGNESS_VALUES = get_args(WillingnessType)
SNAPSHOT_STAGE_VALUES = get_args(SnapshotStageType)
VERIFY_TASK_STATUS_VALUES = get_args(VerifyTaskStatusType)
AI_ENTITY_TYPE_VALUES = get_args(AiEntityType)
AI_EXTRACTION_STATUS_VALUES = get_args(AiExtractionStatusType)

VERIFY_FIELD_VALUES = (
    "age",
    "height_cm",
    "city_code",
    "education_level",
    "marital_status",
    "occupation",
    "smoking_status",
    "drinking_status",
    "pet_status",
)


def sql_in(column_name: str, values: tuple[str, ...]) -> str:
    return f"{column_name} IN ({', '.join(repr(value) for value in values)})"
