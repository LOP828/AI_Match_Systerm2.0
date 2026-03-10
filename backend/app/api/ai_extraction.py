from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor_context, require_privileged_role
from app.audit import audit_log
from app.choices import AiExtractionStatusType
from app.config import Settings, get_settings
from app.db import get_db
from app.models import AiExtraction, InteractionMemo
from app.services.llm_extraction_service import extract_from_memo
from app.time_utils import to_api_datetime, utc_now

router = APIRouter()


@router.get("/")
def get_extractions(
    entityType: str = Query(..., alias="entityType"),
    entityId: int = Query(..., alias="entityId"),
    status: AiExtractionStatusType | None = Query("suggested"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_privileged_role(actor, settings)

    q = db.query(AiExtraction).filter(
        AiExtraction.entity_type == entityType,
        AiExtraction.entity_id == entityId,
    )
    if status:
        q = q.filter(AiExtraction.extraction_status == status)
    items = q.order_by(AiExtraction.created_at.desc(), AiExtraction.extraction_id.desc()).offset(offset).limit(limit).all()
    return [
        {
            "extraction_id": e.extraction_id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "extracted_label": e.extracted_label,
            "extracted_value": e.extracted_value,
            "confidence": float(e.confidence) if e.confidence else None,
            "evidence_text": e.evidence_text,
            "extraction_status": e.extraction_status,
            "reviewed_by": e.reviewed_by,
            "reviewed_at": to_api_datetime(e.reviewed_at),
            "created_at": to_api_datetime(e.created_at),
        }
        for e in items
    ]


def _resolve_reviewer_id(actor: ActorContext, settings: Settings, reviewed_by: int | None) -> int:
    if not settings.auth_required:
        if reviewed_by is None:
            raise HTTPException(status_code=422, detail="reviewedBy is required when auth is disabled")
        return reviewed_by
    if actor.user_id is None:
        raise HTTPException(status_code=401, detail="Missing actor user id")
    return actor.user_id


@router.post("/{extraction_id}/approve")
def approve_extraction(
    extraction_id: int,
    reviewedBy: int | None = Query(None, alias="reviewedBy"),
    request: Request = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_privileged_role(actor, settings)

    ext = db.query(AiExtraction).filter(AiExtraction.extraction_id == extraction_id).first()
    if not ext:
        raise HTTPException(status_code=404, detail="Not found")

    ext.extraction_status = "approved"
    ext.reviewed_by = _resolve_reviewer_id(actor, settings, reviewedBy)
    ext.reviewed_at = utc_now()

    db.commit()
    audit_log("ai_extraction.review", "success", actor=actor, request=request, extractionId=extraction_id, decision="approved", entityType=ext.entity_type, entityId=ext.entity_id)
    return {"success": True}


@router.post("/{extraction_id}/reject")
def reject_extraction(
    extraction_id: int,
    reviewedBy: int | None = Query(None, alias="reviewedBy"),
    request: Request = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_privileged_role(actor, settings)

    ext = db.query(AiExtraction).filter(AiExtraction.extraction_id == extraction_id).first()
    if not ext:
        raise HTTPException(status_code=404, detail="Not found")

    ext.extraction_status = "rejected"
    ext.reviewed_by = _resolve_reviewer_id(actor, settings, reviewedBy)
    ext.reviewed_at = utc_now()
    db.commit()
    audit_log("ai_extraction.review", "success", actor=actor, request=request, extractionId=extraction_id, decision="rejected", entityType=ext.entity_type, entityId=ext.entity_id)
    return {"success": True}


def _run_extraction(memo_id: int) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        extract_from_memo(db, memo_id)
    finally:
        db.close()


@router.post("/trigger/{memo_id}")
def trigger_extraction(
    memo_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_privileged_role(actor, settings)

    if not settings.ai_extraction_enabled:
        raise HTTPException(status_code=503, detail="AI extraction is disabled")
    if not settings.deepseek_api_key:
        raise HTTPException(status_code=503, detail="AI extraction is not configured")

    memo = db.query(InteractionMemo).filter(InteractionMemo.memo_id == memo_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")

    background_tasks.add_task(_run_extraction, memo_id)
    audit_log("ai_extraction.trigger", "success", actor=actor, request=request, memoId=memo_id)
    return {"success": True, "message": "Extraction started in background"}
