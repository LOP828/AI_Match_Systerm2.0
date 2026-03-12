from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.choices import (
    ActiveStatusType,
    ConstraintDirectionType,
    ConstraintStatusType,
    ConstraintTagType,
    DrinkingStatusType,
    GenderType,
    ObservationStatusType,
    ObserverType,
    PetStatusType,
    PreferenceDimensionType,
    PreferenceOperatorType,
    PreferencePriorityType,
    SmokingStatusType,
    VerificationStatusType,
)
from app.profile_fields import is_supported_profile_field
from app.schemas.verify_task import VerifyFieldType


class ProfileBase(BaseModel):
    gender: GenderType | None = None
    age: int | None = Field(default=None, ge=18, le=120)
    height_cm: int | None = Field(default=None, ge=100, le=250)
    city_code: str | None = Field(default=None, max_length=32)
    education_level: str | None = Field(default=None, max_length=32)
    marital_status: str | None = Field(default=None, max_length=32)
    occupation: str | None = Field(default=None, max_length=64)
    smoking_status: SmokingStatusType | None = None
    drinking_status: DrinkingStatusType | None = None
    pet_status: PetStatusType | None = None
    open_to_match: int | None = Field(default=None, ge=0, le=1)
    active_status: ActiveStatusType | None = None
    verification_status: VerificationStatusType | None = None


class ProfileCreate(ProfileBase):
    user_id: int


class ProfileUpdate(ProfileBase):
    model_config = ConfigDict(extra="forbid")


class ProfileResponse(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    profile_completeness: Decimal | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PreferenceCreate(BaseModel):
    dimension: PreferenceDimensionType
    operator: PreferenceOperatorType
    value_json: dict[str, Any] | None = None
    priority_level: PreferencePriorityType | None = None
    source_type: str | None = Field(default=None, max_length=32)


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preference_id: int
    user_id: int
    dimension: PreferenceDimensionType
    operator: PreferenceOperatorType
    value_json: dict[str, Any] | None = None
    priority_level: PreferencePriorityType | None = None
    source_type: str | None = None


class ConstraintCreate(BaseModel):
    tag_code: str = Field(min_length=1, max_length=64)
    tag_type: ConstraintTagType
    applies_to_field: VerifyFieldType
    source_type: str | None = Field(default="matchmaker_input", max_length=32)
    direction: ConstraintDirectionType | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_supported_constraint(self):
        if self.tag_type == "penalty":
            raise ValueError("Constraint tag_type 'penalty' is not supported")
        if not is_supported_profile_field(self.applies_to_field):
            raise ValueError(f"Unsupported applies_to_field: {self.applies_to_field}")
        return self


class ConstraintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    constraint_id: int
    user_id: int
    tag_code: str
    tag_type: ConstraintTagType
    applies_to_field: str | None = None
    source_type: str | None = None
    status: ConstraintStatusType | None = None


class ObservationTagCreate(BaseModel):
    tag_code: str = Field(min_length=1, max_length=64)
    tag_value: str | None = Field(default=None, max_length=64)
    confidence: float | None = Field(default=80, ge=0, le=100)
    observer_type: ObserverType


class ObservationTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tag_id: int
    user_id: int
    tag_code: str
    tag_value: str | None = None
    confidence: float | None = None
    observer_type: ObserverType | None = None
    status: ObservationStatusType | None = None


class ProfileFullResponse(BaseModel):
    profile: ProfileResponse | None = None
    preferences: list[PreferenceResponse] = Field(default_factory=list)
    constraints: list[ConstraintResponse] = Field(default_factory=list)
    tags: list[ObservationTagResponse] = Field(default_factory=list)
