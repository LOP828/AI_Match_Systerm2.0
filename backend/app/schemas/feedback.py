from pydantic import BaseModel, Field, model_validator

from app.choices import WillingnessType


class RecordMeetingRequest(BaseModel):
    userAId: int = Field(gt=0)
    userBId: int = Field(gt=0)
    willingnessA: WillingnessType
    willingnessB: WillingnessType
    conversationSmoothness: int | None = Field(default=None, ge=1, le=5)
    appearanceAcceptance: int | None = Field(default=None, ge=1, le=5)
    valuesAlignment: int | None = Field(default=None, ge=1, le=5)
    rejectReasonPrimary: str | None = Field(default=None, max_length=64)
    rejectReasonSecondary: str | None = Field(default=None, max_length=64)
    issueTagsJson: list[str] | None = None
    memoText: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def validate_distinct_users(self):
        if self.userAId == self.userBId:
            raise ValueError("userAId and userBId must be different")
        return self


class InteractionHistoryItem(BaseModel):
    event_id: int
    event_type: str
    user_a_id: int
    user_b_id: int
    willingness_a: WillingnessType | None
    willingness_b: WillingnessType | None
    conversation_smoothness: int | None = None
    appearance_acceptance: int | None = None
    values_alignment: int | None = None
    reject_reason_primary: str | None = None
    reject_reason_secondary: str | None = None
    issue_tags_json: list[str] | None
    memo_text: str | None
    event_time: str | None
    created_at: str | None


class FeedbackSignals(BaseModel):
    userId: int
    totalMeetings: int
    avgConversationSmoothness: float | None = None
    avgAppearanceAcceptance: float | None = None
    avgValuesAlignment: float | None = None
    topRejectReasons: list[str] = Field(default_factory=list)
    continueRate: float | None = None
