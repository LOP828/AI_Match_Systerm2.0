from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor_context, require_resource_access
from app.audit import audit_log
from app.config import Settings, get_settings
from app.db import get_db
from app.models import UserProfile, VerifyTask
from app.schemas.verify_task import ConfirmVerifyRequest, VerifyTaskResponse
from app.time_utils import to_api_datetime, utc_now

router = APIRouter()

ALLOWED_VERIFY_FIELDS: dict[str, type] = {
    "age": int,
    "height_cm": int,
    "city_code": str,
    "education_level": str,
    "marital_status": str,
    "occupation": str,
    "smoking_status": str,
    "drinking_status": str,
    "pet_status": str,
}


def _normalize_confirmed_value(field: str, raw_value: str) -> Any:
    expected_type = ALLOWED_VERIFY_FIELDS.get(field)
    if expected_type is None:
        raise HTTPException(status_code=400, detail=f"Unsupported verify field: {field}")

    if expected_type is int:
        try:
            return int(raw_value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{field}' requires an integer value",
            ) from exc

    value = str(raw_value).strip()
    if not value:
        raise HTTPException(status_code=422, detail=f"Field '{field}' cannot be empty")
    return value


@router.get("/", response_model=list[VerifyTaskResponse])
def get_verify_tasks(
    requesterUserId: int = Query(..., alias="requesterUserId"),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, requesterUserId, settings)

    q = db.query(VerifyTask).filter(VerifyTask.requester_user_id == requesterUserId)
    if status:
        q = q.filter(VerifyTask.task_status == status)
    tasks = q.order_by(VerifyTask.created_at.desc(), VerifyTask.task_id.desc()).offset(offset).limit(limit).all()
    return [
        VerifyTaskResponse(
            task_id=t.task_id,
            requester_user_id=t.requester_user_id,
            candidate_user_id=t.candidate_user_id,
            verify_field=t.verify_field,
            trigger_reason=t.trigger_reason,
            rough_rank_score=float(t.rough_rank_score) if t.rough_rank_score else None,
            task_status=t.task_status,
            confirmed_value=t.confirmed_value,
            confirmed_by=t.confirmed_by,
            confirmed_at=to_api_datetime(t.confirmed_at),
            created_at=to_api_datetime(t.created_at),
        )
        for t in tasks
    ]


@router.post("/{task_id}/confirm")
def confirm_verify(
    task_id: int,
    body: ConfirmVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    task = db.query(VerifyTask).filter(VerifyTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    require_resource_access(actor, task.requester_user_id, settings)

    if task.task_status != "pending":
        raise HTTPException(status_code=409, detail="Task is not pending")

    candidate = db.query(UserProfile).filter(UserProfile.user_id == task.candidate_user_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    confirmed_value = _normalize_confirmed_value(task.verify_field, body.confirmedValue)

    confirmed_by = body.confirmedBy
    if settings.auth_required:
        if actor.user_id is None:
            raise HTTPException(status_code=401, detail="Missing actor user id")
        confirmed_by = actor.user_id
    elif confirmed_by is None:
        raise HTTPException(status_code=422, detail="confirmedBy is required when auth is disabled")

    setattr(candidate, task.verify_field, confirmed_value)
    task.task_status = "confirmed"
    task.confirmed_value = str(confirmed_value)
    task.confirmed_by = confirmed_by
    task.confirmed_at = utc_now()

    db.commit()
    audit_log(
        "verify_task.confirm",
        "success",
        actor=actor,
        request=request,
        taskId=task.task_id,
        requesterUserId=task.requester_user_id,
        candidateUserId=task.candidate_user_id,
        verifyField=task.verify_field,
        confirmedValue=str(confirmed_value),
    )
    return {"success": True, "confirmedValue": confirmed_value}
