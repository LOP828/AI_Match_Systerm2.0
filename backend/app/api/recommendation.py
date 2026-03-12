from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor_context, require_resource_access
from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.recommendation import GenerateRequest, GenerateResponse, RegenerateRequest, RegenerateResponse, SnapshotResponse
from app.services.recommendation_service import generate_candidates, get_recommendations, regenerate_candidates
from app.time_utils import to_api_datetime

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def post_generate(
    body: GenerateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, body.requesterUserId, settings)
    filters = body.filters.model_dump() if body.filters else {}
    return generate_candidates(db, body.requesterUserId, filters)


@router.post("/regenerate/{requester_id}", response_model=RegenerateResponse)
def post_regenerate(
    requester_id: int,
    body: RegenerateRequest | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, requester_id, settings)
    top_n = body.topN if body else 5
    return regenerate_candidates(db, requester_id, top_n=top_n)


@router.get("/{requester_id}", response_model=list[SnapshotResponse])
def get_recommendation_snapshots(
    requester_id: int,
    stage: Literal["rough", "verified", "final"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, requester_id, settings)
    snapshots = get_recommendations(db, requester_id, stage, limit=limit, offset=offset)
    return [
        SnapshotResponse(
            rec_id=s.rec_id,
            requester_user_id=s.requester_user_id,
            candidate_user_id=s.candidate_user_id,
            safety_score=float(s.safety_score) if s.safety_score else None,
            chat_score=float(s.chat_score) if s.chat_score else None,
            second_date_score=float(s.second_date_score) if s.second_date_score else None,
            conflict_risk_score=float(s.conflict_risk_score) if s.conflict_risk_score else None,
            final_rank_score=float(s.final_rank_score) if s.final_rank_score else None,
            snapshot_stage=s.snapshot_stage,
            explanation_json=s.explanation_json,
            verify_pending_count=s.verify_pending_count,
            created_at=to_api_datetime(s.created_at),
        )
        for s in snapshots
    ]
