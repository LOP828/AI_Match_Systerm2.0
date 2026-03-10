from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import RecommendationSnapshot, UserProfile, VerifyTask
from app.services.ranking_service import calculate_multi_scores
from app.services.rule_engine import (
    collect_unknown_constraints,
    evaluate_block_constraints,
    filter_by_hard_rules,
    get_active_constraints,
)
from app.time_utils import utc_now


def _profile_to_dict(p: UserProfile | None) -> dict[str, Any] | None:
    if not p:
        return None
    return {
        "userId": p.user_id,
        "gender": p.gender,
        "age": p.age,
        "heightCm": p.height_cm,
        "cityCode": p.city_code,
        "educationLevel": p.education_level,
        "maritalStatus": p.marital_status,
        "occupation": p.occupation,
        "smokingStatus": p.smoking_status,
        "drinkingStatus": p.drinking_status,
        "petStatus": p.pet_status,
    }


def _score_average(scores: dict[str, Decimal]) -> float:
    return (
        float(scores["safetyScore"])
        + float(scores["chatScore"])
        + float(scores["secondDateScore"])
    ) / 3


def generate_candidates(
    db: Session,
    requester_user_id: int,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate rough candidates and pending verify tasks with idempotent persistence."""
    filters = filters or {}
    filter_dict = {
        "ageMin": filters.get("ageMin"),
        "ageMax": filters.get("ageMax"),
        "heightMin": filters.get("heightMin"),
        "heightMax": filters.get("heightMax"),
        "cities": filters.get("cities"),
        "educationLevels": filters.get("educationLevels"),
        "maritalStatuses": filters.get("maritalStatuses"),
    }

    requester = db.query(UserProfile).filter(UserProfile.user_id == requester_user_id).first()
    if not requester:
        return {
            "basicCandidatesCount": 0,
            "safeCandidatesCount": 0,
            "topCandidates": [],
        }

    basic_ids = filter_by_hard_rules(db, requester_user_id, filter_dict)
    basic_count = len(basic_ids)

    if not basic_ids:
        return {
            "basicCandidatesCount": 0,
            "safeCandidatesCount": 0,
            "topCandidates": [],
        }

    all_active_constraints, block_constraints, verify_constraints = get_active_constraints(
        db, requester_user_id
    )

    candidate_profiles = db.query(UserProfile).filter(UserProfile.user_id.in_(basic_ids)).all()
    profiles_by_id = {profile.user_id: profile for profile in candidate_profiles}

    safe_candidates: list[UserProfile] = []
    for candidate_id in basic_ids:
        candidate = profiles_by_id.get(candidate_id)
        if not candidate:
            continue
        blocked, _ = evaluate_block_constraints(candidate, block_constraints)
        if not blocked:
            safe_candidates.append(candidate)

    safe_count = len(safe_candidates)

    candidates_with_scores: list[dict[str, Any]] = []
    for candidate in safe_candidates:
        scores = calculate_multi_scores(requester, candidate, all_active_constraints)
        unknown = collect_unknown_constraints(candidate, verify_constraints)
        candidates_with_scores.append(
            {
                "candidateId": candidate.user_id,
                "profile": candidate,
                "scores": scores,
                "unknownConstraints": unknown,
                "unknownConstraintCount": len(unknown),
            }
        )

    def sort_key(x: dict[str, Any]) -> float:
        avg = _score_average(x["scores"])
        return avg - x["unknownConstraintCount"] * 10

    candidates_with_scores.sort(key=sort_key, reverse=True)
    top_n = candidates_with_scores[:10]
    top_candidate_ids = [item["candidateId"] for item in top_n]

    existing_snapshots: dict[int, RecommendationSnapshot] = {}
    if top_candidate_ids:
        rows = (
            db.query(RecommendationSnapshot)
            .filter(
                RecommendationSnapshot.requester_user_id == requester_user_id,
                RecommendationSnapshot.snapshot_stage == "rough",
                RecommendationSnapshot.candidate_user_id.in_(top_candidate_ids),
            )
            .order_by(RecommendationSnapshot.created_at.desc(), RecommendationSnapshot.rec_id.desc())
            .all()
        )
        for row in rows:
            if row.candidate_user_id not in existing_snapshots:
                existing_snapshots[row.candidate_user_id] = row
            else:
                db.delete(row)

    pending_tasks: dict[tuple[int, str], VerifyTask] = {}
    if top_candidate_ids:
        rows = (
            db.query(VerifyTask)
            .filter(
                VerifyTask.requester_user_id == requester_user_id,
                VerifyTask.task_status == "pending",
                VerifyTask.candidate_user_id.in_(top_candidate_ids),
            )
            .order_by(VerifyTask.created_at.desc(), VerifyTask.task_id.desc())
            .all()
        )
        for row in rows:
            key = (row.candidate_user_id, row.verify_field)
            if key not in pending_tasks:
                pending_tasks[key] = row
            else:
                db.delete(row)

    timestamp = utc_now()

    for candidate in top_n:
        candidate_id = candidate["candidateId"]
        scores = candidate["scores"]
        final_average = _score_average(scores)
        sort_score = sort_key(candidate)

        snap = existing_snapshots.get(candidate_id)
        if not snap:
            snap = RecommendationSnapshot(
                requester_user_id=requester_user_id,
                candidate_user_id=candidate_id,
                snapshot_stage="rough",
            )
            db.add(snap)

        snap.safety_score = scores["safetyScore"]
        snap.chat_score = scores["chatScore"]
        snap.second_date_score = scores["secondDateScore"]
        snap.conflict_risk_score = scores["conflictRiskScore"]
        snap.verify_count = candidate["unknownConstraintCount"]
        snap.final_rank_score = Decimal(str(sort_score))
        snap.verify_pending_count = candidate["unknownConstraintCount"]
        snap.rank_change_reason = "reranked_with_unknown_penalty"
        snap.explanation_json = {
            "reason": "rough_ranking",
            "sortScore": round(sort_score, 2),
            "baseAverage": round(final_average, 2),
            "unknownConstraintCount": candidate["unknownConstraintCount"],
        }
        snap.created_at = timestamp

        for uc in candidate["unknownConstraints"]:
            verify_field = uc.applies_to_field
            if not verify_field:
                continue
            key = (candidate_id, verify_field)
            task = pending_tasks.get(key)
            if task:
                task.trigger_reason = f"Top10 candidate requires confirmation of {uc.tag_code}"
                task.rough_rank_score = Decimal(str(sort_score))
                continue

            task = VerifyTask(
                requester_user_id=requester_user_id,
                candidate_user_id=candidate_id,
                verify_field=verify_field,
                trigger_reason=f"Top10 candidate requires confirmation of {uc.tag_code}",
                rough_rank_score=Decimal(str(sort_score)),
                task_status="pending",
            )
            db.add(task)
            pending_tasks[key] = task

    db.commit()

    return {
        "basicCandidatesCount": basic_count,
        "safeCandidatesCount": safe_count,
        "topCandidates": [
            {
                "candidateId": t["candidateId"],
                "profile": _profile_to_dict(t["profile"]),
                "scores": {
                    "safetyScore": float(t["scores"]["safetyScore"]),
                    "chatScore": float(t["scores"]["chatScore"]),
                    "secondDateScore": float(t["scores"]["secondDateScore"]),
                    "conflictRiskScore": float(t["scores"]["conflictRiskScore"]),
                },
                "unknownConstraintCount": t["unknownConstraintCount"],
                "unknownConstraints": [
                    {"tagCode": u.tag_code, "appliesToField": u.applies_to_field}
                    for u in t["unknownConstraints"]
                ],
            }
            for t in top_n
        ],
    }


def get_recommendations(
    db: Session,
    requester_user_id: int,
    stage: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RecommendationSnapshot]:
    q = db.query(RecommendationSnapshot).filter(
        RecommendationSnapshot.requester_user_id == requester_user_id
    )
    if stage:
        q = q.filter(RecommendationSnapshot.snapshot_stage == stage)
    return (
        q.order_by(RecommendationSnapshot.created_at.desc(), RecommendationSnapshot.rec_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
