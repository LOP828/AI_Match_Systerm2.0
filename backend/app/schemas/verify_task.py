from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.choices import VerifyTaskStatusType

VerifyFieldType = Literal[
    "age",
    "height_cm",
    "city_code",
    "education_level",
    "marital_status",
    "occupation",
    "smoking_status",
    "drinking_status",
    "pet_status",
]


class VerifyTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    requester_user_id: int
    candidate_user_id: int
    verify_field: VerifyFieldType
    trigger_reason: str | None = None
    rough_rank_score: float | None = None
    task_status: VerifyTaskStatusType | None = None
    confirmed_value: str | None = None
    confirmed_by: int | None = None
    confirmed_at: str | None = None
    created_at: str | None = None


class ConfirmVerifyRequest(BaseModel):
    confirmedValue: str = Field(min_length=1, max_length=128)
    confirmedBy: int | None = Field(default=None, gt=0)
