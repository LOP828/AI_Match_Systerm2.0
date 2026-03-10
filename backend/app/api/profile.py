from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ActorContext, get_actor_context, require_resource_access
from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.profile import (
    ConstraintCreate,
    ConstraintResponse,
    ObservationTagCreate,
    ObservationTagResponse,
    PreferenceCreate,
    PreferenceResponse,
    ProfileFullResponse,
    ProfileResponse,
    ProfileUpdate,
)
from app.services.profile_service import (
    add_user_constraint,
    add_user_observation_tag,
    add_user_preference,
    get_user_constraints,
    get_user_observation_tags,
    get_user_preferences,
    get_user_profile,
    upsert_user_profile,
)
from app.time_utils import to_api_datetime

router = APIRouter()


def _profile_to_response(p) -> ProfileResponse | None:
    if p is None:
        return None
    return ProfileResponse(
        user_id=p.user_id,
        gender=p.gender,
        age=p.age,
        height_cm=p.height_cm,
        city_code=p.city_code,
        education_level=p.education_level,
        marital_status=p.marital_status,
        occupation=p.occupation,
        smoking_status=p.smoking_status,
        drinking_status=p.drinking_status,
        pet_status=p.pet_status,
        open_to_match=p.open_to_match,
        active_status=p.active_status,
        profile_completeness=p.profile_completeness,
        verification_status=p.verification_status,
        created_at=to_api_datetime(p.created_at),
        updated_at=to_api_datetime(p.updated_at),
    )


@router.get("/{user_id}", response_model=ProfileFullResponse)
def get_profile(
    user_id: int,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, user_id, settings)

    profile = get_user_profile(db, user_id)
    preferences = get_user_preferences(db, user_id)
    constraints = get_user_constraints(db, user_id)
    tags = get_user_observation_tags(db, user_id)

    return ProfileFullResponse(
        profile=_profile_to_response(profile),
        preferences=[
            PreferenceResponse(
                preference_id=p.preference_id,
                user_id=p.user_id,
                dimension=p.dimension,
                operator=p.operator,
                value_json=p.value_json,
                priority_level=p.priority_level,
                source_type=p.source_type,
            )
            for p in preferences
        ],
        constraints=[
            ConstraintResponse(
                constraint_id=c.constraint_id,
                user_id=c.user_id,
                tag_code=c.tag_code,
                tag_type=c.tag_type,
                applies_to_field=c.applies_to_field,
                source_type=c.source_type,
                status=c.status,
            )
            for c in constraints
        ],
        tags=[
            ObservationTagResponse(
                tag_id=t.tag_id,
                user_id=t.user_id,
                tag_code=t.tag_code,
                tag_value=t.tag_value,
                confidence=float(t.confidence) if t.confidence else None,
                observer_type=t.observer_type,
                status=t.status,
            )
            for t in tags
        ],
    )


@router.post("/{user_id}", response_model=ProfileResponse)
def update_profile(
    user_id: int,
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, user_id, settings)

    update_dict: dict[str, Any] = data.model_dump(exclude_unset=True)
    profile = upsert_user_profile(db, user_id, update_dict)
    return _profile_to_response(profile)


@router.post("/{user_id}/preference", response_model=PreferenceResponse)
def add_preference(
    user_id: int,
    data: PreferenceCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, user_id, settings)

    try:
        pref = add_user_preference(db, user_id, data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PreferenceResponse(
        preference_id=pref.preference_id,
        user_id=pref.user_id,
        dimension=pref.dimension,
        operator=pref.operator,
        value_json=pref.value_json,
        priority_level=pref.priority_level,
        source_type=pref.source_type,
    )


@router.post("/{user_id}/constraint", response_model=ConstraintResponse)
def add_constraint(
    user_id: int,
    data: ConstraintCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, user_id, settings)

    try:
        constraint = add_user_constraint(db, user_id, data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ConstraintResponse(
        constraint_id=constraint.constraint_id,
        user_id=constraint.user_id,
        tag_code=constraint.tag_code,
        tag_type=constraint.tag_type,
        applies_to_field=constraint.applies_to_field,
        source_type=constraint.source_type,
        status=constraint.status,
    )


@router.post("/{user_id}/observation-tag", response_model=ObservationTagResponse)
def add_observation_tag(
    user_id: int,
    data: ObservationTagCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_actor_context),
    settings: Settings = Depends(get_settings),
):
    require_resource_access(actor, user_id, settings)

    try:
        tag = add_user_observation_tag(db, user_id, data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ObservationTagResponse(
        tag_id=tag.tag_id,
        user_id=tag.user_id,
        tag_code=tag.tag_code,
        tag_value=tag.tag_value,
        confidence=float(tag.confidence) if tag.confidence else None,
        observer_type=tag.observer_type,
        status=tag.status,
    )
