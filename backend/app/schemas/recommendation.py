from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.choices import SnapshotStageType


class GenerateFilters(BaseModel):
    ageMin: int | None = Field(default=None, ge=18, le=120)
    ageMax: int | None = Field(default=None, ge=18, le=120)
    heightMin: int | None = Field(default=None, ge=100, le=250)
    heightMax: int | None = Field(default=None, ge=100, le=250)
    cities: list[str] | None = None
    educationLevels: list[str] | None = None
    maritalStatuses: list[str] | None = None


class GenerateRequest(BaseModel):
    requesterUserId: int
    filters: GenerateFilters | None = None


class CandidateScore(BaseModel):
    safetyScore: float
    chatScore: float
    secondDateScore: float
    conflictRiskScore: float


class TopCandidate(BaseModel):
    candidateId: int
    profile: dict[str, Any] | None = None
    scores: CandidateScore
    unknownConstraintCount: int = 0
    unknownConstraints: list[dict[str, Any]] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    basicCandidatesCount: int
    safeCandidatesCount: int
    topCandidates: list[TopCandidate]


class RegenerateRequest(BaseModel):
    topN: int = Field(default=5, ge=1, le=20)


class RegenerateItem(BaseModel):
    candidateId: int
    score: float
    rank: int


class RegenerateResponse(BaseModel):
    requesterId: int
    stage: str
    usedConfirmedVerifyTasks: int
    items: list[RegenerateItem]


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rec_id: int
    requester_user_id: int
    candidate_user_id: int
    safety_score: float | None = None
    chat_score: float | None = None
    second_date_score: float | None = None
    conflict_risk_score: float | None = None
    final_rank_score: float | None = None
    snapshot_stage: SnapshotStageType | None = None
    explanation_json: dict[str, Any] | None = None
    verify_pending_count: int | None = None
    created_at: str | None = None
