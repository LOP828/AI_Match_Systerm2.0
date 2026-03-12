from datetime import timedelta
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor_context, require_privileged_role
from app.audit import audit_log
from app.choices import AiExtractionStatusType
from app.config import Settings, get_settings
from app.db import get_db
from app.models import AiExtraction, InteractionEvent, InteractionMemo, UserConstraint, UserObservationTag, UserProfile, VerifyTask
from app.profile_fields import is_supported_profile_field, normalize_profile_field_value
from app.services.llm_extraction_service import extract_from_memo
from app.time_utils import to_api_datetime, utc_now

router = APIRouter()

EXTRACTION_TRIGGER_LABEL = "__trigger_job__"
EXTRACTION_TRIGGER_STALE_AFTER = timedelta(minutes=15)

PROFILE_FIELD_ALIASES: dict[str, str] = {
    "age": "age",
    "height": "height_cm",
    "height_cm": "height_cm",
    "city": "city_code",
    "city_code": "city_code",
    "education": "education_level",
    "education_level": "education_level",
    "marriage": "marital_status",
    "marital": "marital_status",
    "marital_status": "marital_status",
    "occupation": "occupation",
    "job": "occupation",
    "work": "occupation",
    "smoking": "smoking_status",
    "smoker": "smoking_status",
    "smoking_status": "smoking_status",
    "drink": "drinking_status",
    "drinking": "drinking_status",
    "alcohol": "drinking_status",
    "drinking_status": "drinking_status",
    "pet": "pet_status",
    "cat": "pet_status",
    "dog": "pet_status",
    "pet_status": "pet_status",
}


def _infer_profile_field(label: str | None) -> str | None:
    if not label:
        return None

    normalized = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    if normalized in PROFILE_FIELD_ALIASES:
        return PROFILE_FIELD_ALIASES[normalized]

    parts = [part for part in normalized.split("_") if part]
    for part in parts:
        if part in PROFILE_FIELD_ALIASES:
            return PROFILE_FIELD_ALIASES[part]

    for alias, field in PROFILE_FIELD_ALIASES.items():
        if alias in normalized:
            return field
    return None


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
            "extraction_type": e.extraction_type,
            "confidence": float(e.confidence) if e.confidence else None,
            "evidence_text": e.evidence_text,
            "extraction_status": e.extraction_status,
            "suggested_action": _suggest_action(e),
            "reviewed_by": e.reviewed_by,
            "reviewed_at": to_api_datetime(e.reviewed_at),
            "created_at": to_api_datetime(e.created_at),
        }
        for e in items
    ]


def _suggest_action(ext: AiExtraction) -> str:
    """Return the suggested writeback action for an extraction."""
    if ext.extraction_type == "observation":
        return "create_observation_tag"
    if ext.extraction_type == "risk":
        target_field = _infer_profile_field(ext.extracted_label)
        if target_field is None:
            return "none"
        if not is_supported_profile_field(target_field):
            return "none"
        try:
            normalize_profile_field_value(target_field, ext.extracted_value)
        except ValueError:
            return "create_verify_task"
        conf = float(ext.confidence) if ext.confidence else 0
        if conf >= 70:
            return "create_constraint"
        return "create_verify_task"
    return "none"


def _resolve_target_user_id(db: Session, ext: AiExtraction) -> int | None:
    """Derive the target user from the extraction's memo -> event chain.

    Convention: user_b_id is always the candidate being observed;
    user_a_id is the requester (matchmaker's client).  This mirrors the
    record_meeting() call in feedback_service where user_a is the
    requester and user_b is the candidate.
    """
    if ext.entity_type != "memo":
        return None
    memo = db.query(InteractionMemo).filter(InteractionMemo.memo_id == ext.entity_id).first()
    if not memo:
        return None
    event = db.query(InteractionEvent).filter(InteractionEvent.event_id == memo.related_event_id).first()
    if not event:
        return None
    return event.user_b_id


def _build_trigger_job_key(memo_id: int) -> str:
    return f"memo:{memo_id}"


def _reserve_extraction_job(
    db: Session,
    memo_id: int,
    *,
    now=None,
    stale_after: timedelta = EXTRACTION_TRIGGER_STALE_AFTER,
) -> AiExtraction:
    current_time = now or utc_now()
    stale_before = current_time - stale_after
    job_key = _build_trigger_job_key(memo_id)

    stale_jobs = (
        db.query(AiExtraction)
        .filter(
            AiExtraction.job_key == job_key,
            AiExtraction.created_at < stale_before,
        )
        .all()
    )
    for stale_job in stale_jobs:
        db.delete(stale_job)
    if stale_jobs:
        db.flush()

    existing = (
        db.query(AiExtraction.extraction_id)
        .filter(
            AiExtraction.entity_type == "memo",
            AiExtraction.entity_id == memo_id,
            AiExtraction.extraction_status.in_(["suggested", "approved"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Extraction already exists for this memo. Reject existing records first to re-trigger.",
        )

    trigger_job = AiExtraction(
        entity_type="memo",
        entity_id=memo_id,
        extracted_label=EXTRACTION_TRIGGER_LABEL,
        extraction_status=None,
        job_key=job_key,
    )
    db.add(trigger_job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Extraction is already running for this memo. Wait for it to finish before retrying.",
        ) from exc
    db.refresh(trigger_job)
    return trigger_job


def _apply_writeback(db: Session, ext: AiExtraction) -> dict:
    """Create business entities based on approved extraction. Returns action result."""
    action = _suggest_action(ext)
    target_user_id = _resolve_target_user_id(db, ext)
    target_field = _infer_profile_field(ext.extracted_label)

    if not target_user_id or action == "none":
        return {"appliedAction": "none"}

    if action == "create_observation_tag":
        tag = UserObservationTag(
            user_id=target_user_id,
            tag_code=(ext.extracted_label or "")[:100],
            tag_value=ext.extracted_value,
            confidence=ext.confidence,
            observer_type="ai",
            source_ref_id=ext.extraction_id,
            status="approved",
        )
        db.add(tag)
        db.flush()
        return {
            "appliedAction": "create_observation_tag",
            "targetEntity": "user_observation_tag",
            "createdObservationTagId": tag.tag_id,
        }

    if action == "create_constraint":
        if not target_field or not is_supported_profile_field(target_field):
            return {"appliedAction": "none"}
        target_user = db.query(UserProfile).filter(UserProfile.user_id == target_user_id).first()
        if not target_user:
            return {"appliedAction": "none"}
        normalized_value = normalize_profile_field_value(target_field, ext.extracted_value)
        setattr(target_user, target_field, normalized_value)

        constraint = UserConstraint(
            user_id=target_user_id,
            tag_code=(ext.extracted_label or "")[:100],
            tag_type="block",
            applies_to_field=target_field,
            source_type="ai_extraction",
            source_ref_id=ext.extraction_id,
            is_human_confirmed=1,
            status="active",
        )
        db.add(constraint)
        db.flush()
        return {
            "appliedAction": "create_constraint",
            "targetEntity": "user_constraint",
            "createdConstraintId": constraint.constraint_id,
            "writtenProfileField": target_field,
            "writtenProfileValue": str(normalized_value),
        }

    if action == "create_verify_task":
        memo = db.query(InteractionMemo).filter(InteractionMemo.memo_id == ext.entity_id).first()
        event = db.query(InteractionEvent).filter(InteractionEvent.event_id == memo.related_event_id).first() if memo else None
        requester_id = event.user_a_id if event else target_user_id
        task = VerifyTask(
            requester_user_id=requester_id,
            candidate_user_id=target_user_id,
            verify_field=target_field,
            trigger_reason=f"AI extraction #{ext.extraction_id}: {ext.evidence_text or ext.extracted_label}"[:255],
            task_status="pending",
        )
        db.add(task)
        db.flush()
        return {
            "appliedAction": "create_verify_task",
            "targetEntity": "verify_task",
            "createdVerifyTaskId": task.task_id,
        }

    return {"appliedAction": "none"}


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

    if ext.extraction_status != "suggested":
        raise HTTPException(
            status_code=409,
            detail=f"Extraction already reviewed (status: {ext.extraction_status})",
        )

    ext.extraction_status = "approved"
    ext.reviewed_by = _resolve_reviewer_id(actor, settings, reviewedBy)
    ext.reviewed_at = utc_now()

    writeback_result = _apply_writeback(db, ext)

    db.commit()
    audit_log("ai_extraction.review", "success", actor=actor, request=request, extractionId=extraction_id, decision="approved", entityType=ext.entity_type, entityId=ext.entity_id, **writeback_result)
    return {
        "success": True,
        "extractionId": extraction_id,
        "status": "approved",
        **writeback_result,
    }


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

    if ext.extraction_status != "suggested":
        raise HTTPException(
            status_code=409,
            detail=f"Extraction already reviewed (status: {ext.extraction_status})",
        )

    ext.extraction_status = "rejected"
    ext.reviewed_by = _resolve_reviewer_id(actor, settings, reviewedBy)
    ext.reviewed_at = utc_now()
    db.commit()
    audit_log("ai_extraction.review", "success", actor=actor, request=request, extractionId=extraction_id, decision="rejected", entityType=ext.entity_type, entityId=ext.entity_id)
    return {"success": True}


def _run_extraction(memo_id: int, trigger_job_id: int) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        extract_from_memo(db, memo_id, trigger_job_id=trigger_job_id)
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

    trigger_job = _reserve_extraction_job(db, memo_id)

    background_tasks.add_task(_run_extraction, memo_id, trigger_job.extraction_id)
    audit_log("ai_extraction.trigger", "success", actor=actor, request=request, memoId=memo_id, triggerJobId=trigger_job.extraction_id)
    return {"success": True, "message": "Extraction started in background", "triggerJobId": trigger_job.extraction_id}
