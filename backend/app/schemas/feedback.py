from pydantic import BaseModel, Field

from app.choices import WillingnessType


class RecordMeetingRequest(BaseModel):
    userAId: int = Field(gt=0)
    userBId: int = Field(gt=0)
    willingnessA: WillingnessType
    willingnessB: WillingnessType
    issueTagsJson: list[str] | None = None
    memoText: str = Field(default="", max_length=4000)


class InteractionHistoryItem(BaseModel):
    event_id: int
    event_type: str
    user_a_id: int
    user_b_id: int
    willingness_a: WillingnessType | None
    willingness_b: WillingnessType | None
    issue_tags_json: list[str] | None
    memo_text: str | None
    event_time: str | None
    created_at: str | None
