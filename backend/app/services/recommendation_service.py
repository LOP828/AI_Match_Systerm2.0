from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InteractionEvent, RecommendationSnapshot, UserPreference, UserProfile, VerifyTask
from app.profile_fields import is_supported_profile_field
from app.services.ranking_service import calculate_multi_scores, score_soft_preferences
from app.services.rule_engine import (
    collect_unknown_constraints,
    evaluate_block_constraints,
    filter_by_hard_rules,
    get_active_constraints,
)
from app.time_utils import utc_now


def _batch_feedback_signals(db: Session, user_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Load feedback signals for multiple users in two queries instead of N queries."""
    if not user_ids:
        return {}

    id_set = set(user_ids)
    events = (
        db.query(InteractionEvent)
        .filter(
            InteractionEvent.event_type == "meet",
            or_(
                InteractionEvent.user_a_id.in_(id_set),
                InteractionEvent.user_b_id.in_(id_set),
            ),
        )
        .limit(min(len(user_ids) * 200, 10_000))
        .all()
    )

    # Group events by user — each event can appear for both sides
    events_by_user: dict[int, list[InteractionEvent]] = {uid: [] for uid in user_ids}
    for e in events:
        if e.user_a_id in events_by_user:
            events_by_user[e.user_a_id].append(e)
        if e.user_b_id in events_by_user:
            events_by_user[e.user_b_id].append(e)

    result: dict[int, dict[str, Any]] = {}
    for uid in user_ids:
        evts = events_by_user[uid]
        total = len(evts)
        if total == 0:
            result[uid] = {
                "userId": uid, "totalMeetings": 0,
                "avgConversationSmoothness": None, "avgAppearanceAcceptance": None,
                "avgValuesAlignment": None, "topRejectReasons": [], "continueRate": None,
            }
            continue

        smoothness_vals = [e.conversation_smoothness for e in evts if e.conversation_smoothness is not None]
        appearance_vals = [e.appearance_acceptance for e in evts if e.appearance_acceptance is not None]
        alignment_vals = [e.values_alignment for e in evts if e.values_alignment is not None]
        reject_reasons: list[str] = []
        continue_count = 0
        for e in evts:
            if e.reject_reason_primary:
                reject_reasons.append(e.reject_reason_primary)
            if e.reject_reason_secondary:
                reject_reasons.append(e.reject_reason_secondary)
            if e.user_a_id == uid and e.willingness_a == "yes":
                continue_count += 1
            elif e.user_b_id == uid and e.willingness_b == "yes":
                continue_count += 1

        result[uid] = {
            "userId": uid,
            "totalMeetings": total,
            "avgConversationSmoothness": round(sum(smoothness_vals) / len(smoothness_vals), 2) if smoothness_vals else None,
            "avgAppearanceAcceptance": round(sum(appearance_vals) / len(appearance_vals), 2) if appearance_vals else None,
            "avgValuesAlignment": round(sum(alignment_vals) / len(alignment_vals), 2) if alignment_vals else None,
            "topRejectReasons": [r for r, _ in Counter(reject_reasons).most_common(3)],
            "continueRate": round(continue_count / total, 2),
        }
    return result


def _feedback_adjustment(signals: dict[str, Any]) -> float:
    """Calculate a score adjustment based on historical feedback signals.

    Returns a bonus/penalty value (roughly -10 to +10) that can be added to
    the sort score of a candidate.
    """
    if signals["totalMeetings"] == 0:
        return 0.0

    adjustment = 0.0

    # Continue rate bonus/penalty: high willingness is a positive signal
    if signals["continueRate"] is not None:
        # continueRate 0.0-1.0 → adjustment -5 to +5
        adjustment += (signals["continueRate"] - 0.5) * 10

    # Average rating bonus (each metric 1-5, midpoint 3)
    rating_count = 0
    rating_sum = 0.0
    for key in ("avgConversationSmoothness", "avgAppearanceAcceptance", "avgValuesAlignment"):
        val = signals.get(key)
        if val is not None:
            rating_sum += (val - 3.0)  # deviation from midpoint
            rating_count += 1
    if rating_count > 0:
        # average deviation * 2 → roughly -4 to +4
        adjustment += (rating_sum / rating_count) * 2

    return round(adjustment, 2)


def _count_used_confirmed_tasks(
    db: Session,
    requester_user_id: int,
    candidate_ids: list[int],
) -> int:
    if not candidate_ids:
        return 0
    return (
        db.query(VerifyTask)
        .filter(
            VerifyTask.requester_user_id == requester_user_id,
            VerifyTask.task_status == "confirmed",
            VerifyTask.candidate_user_id.in_(candidate_ids),
        )
        .count()
    )


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
    retry_on_conflict: bool = True,
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
    requester_preferences = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == requester_user_id)
        .all()
    )

    basic_ids = filter_by_hard_rules(db, requester_user_id, filter_dict)
    basic_count = len(basic_ids)

    if not basic_ids:
        return {
            "basicCandidatesCount": 0,
            "safeCandidatesCount": 0,
            "topCandidates": [],
        }

    _, block_constraints, verify_constraints = get_active_constraints(
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

    safe_candidate_ids = [candidate.user_id for candidate in safe_candidates]
    used_confirmed_task_count = _count_used_confirmed_tasks(
        db,
        requester_user_id,
        safe_candidate_ids,
    )

    candidates_with_scores: list[dict[str, Any]] = []
    for candidate in safe_candidates:
        soft_preference = score_soft_preferences(candidate, requester_preferences)
        unknown = collect_unknown_constraints(candidate, verify_constraints)
        scores = calculate_multi_scores(
            requester,
            candidate,
            unknown_constraint_count=len(unknown),
            preference_adjustment=soft_preference["adjustment"],
        )
        candidates_with_scores.append(
            {
                "candidateId": candidate.user_id,
                "profile": candidate,
                "scores": scores,
                "softPreference": soft_preference,
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
            "softPreferenceScore": float(candidate["softPreference"]["adjustment"]),
            "softPreferenceApplied": candidate["softPreference"]["applied"],
            "softPreferenceUnmet": candidate["softPreference"]["unmet"],
            "softPreferenceUnknown": candidate["softPreference"]["unknown"],
        }
        snap.created_at = timestamp

        for uc in candidate["unknownConstraints"]:
            verify_field = uc.applies_to_field
            if not is_supported_profile_field(verify_field):
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not retry_on_conflict:
            raise
        return generate_candidates(
            db,
            requester_user_id=requester_user_id,
            filters=filters,
            retry_on_conflict=False,
        )

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


def regenerate_candidates(
    db: Session,
    requester_user_id: int,
    top_n: int = 5,
    retry_on_conflict: bool = True,
) -> dict[str, Any]:
    """Re-rank candidates using updated profiles after verify tasks are confirmed.

    Generates verified-stage snapshots. Unlike rough ranking, confirmed fields
    are no longer treated as unknown so the penalty is reduced.
    """
    requester = db.query(UserProfile).filter(UserProfile.user_id == requester_user_id).first()
    if not requester:
        return {
            "requesterId": requester_user_id,
            "stage": "verified",
            "usedConfirmedVerifyTasks": 0,
            "items": [],
        }
    requester_preferences = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == requester_user_id)
        .all()
    )

    basic_ids = filter_by_hard_rules(db, requester_user_id, {})
    if not basic_ids:
        return {
            "requesterId": requester_user_id,
            "stage": "verified",
            "usedConfirmedVerifyTasks": 0,
            "items": [],
        }

    _, block_constraints, verify_constraints = get_active_constraints(
        db, requester_user_id
    )

    candidate_profiles = db.query(UserProfile).filter(UserProfile.user_id.in_(basic_ids)).all()
    profiles_by_id = {p.user_id: p for p in candidate_profiles}

    safe_candidates: list[UserProfile] = []
    for cid in basic_ids:
        candidate = profiles_by_id.get(cid)
        if not candidate:
            continue
        blocked, _ = evaluate_block_constraints(candidate, block_constraints)
        if not blocked:
            safe_candidates.append(candidate)

    safe_candidate_ids = [candidate.user_id for candidate in safe_candidates]
    used_confirmed_task_count = _count_used_confirmed_tasks(
        db,
        requester_user_id,
        safe_candidate_ids,
    )

    # Batch-load feedback signals for all safe candidates in two queries
    all_signals = _batch_feedback_signals(db, [c.user_id for c in safe_candidates])

    candidates_with_scores: list[dict[str, Any]] = []
    for candidate in safe_candidates:
        soft_preference = score_soft_preferences(candidate, requester_preferences)
        unknown = collect_unknown_constraints(candidate, verify_constraints)
        scores = calculate_multi_scores(
            requester,
            candidate,
            unknown_constraint_count=len(unknown),
            preference_adjustment=soft_preference["adjustment"],
        )
        fb_adj = _feedback_adjustment(all_signals.get(candidate.user_id, {"totalMeetings": 0}))

        candidates_with_scores.append(
            {
                "candidateId": candidate.user_id,
                "scores": scores,
                "softPreference": soft_preference,
                "unknownConstraintCount": len(unknown),
                "feedbackAdjustment": fb_adj,
            }
        )

    def sort_key(x: dict[str, Any]) -> float:
        avg = _score_average(x["scores"])
        return avg - x["unknownConstraintCount"] * 10 + x["feedbackAdjustment"]

    candidates_with_scores.sort(key=sort_key, reverse=True)
    top_candidates = candidates_with_scores[:top_n]
    top_candidate_ids = [item["candidateId"] for item in top_candidates]

    existing_snapshots: dict[int, RecommendationSnapshot] = {}
    if top_candidate_ids:
        rows = (
            db.query(RecommendationSnapshot)
            .filter(
                RecommendationSnapshot.requester_user_id == requester_user_id,
                RecommendationSnapshot.snapshot_stage == "verified",
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

    timestamp = utc_now()
    result_items: list[dict[str, Any]] = []

    for rank, candidate in enumerate(top_candidates, start=1):
        candidate_id = candidate["candidateId"]
        scores = candidate["scores"]
        final_average = _score_average(scores)
        score = sort_key(candidate)

        snap = existing_snapshots.get(candidate_id)
        if not snap:
            snap = RecommendationSnapshot(
                requester_user_id=requester_user_id,
                candidate_user_id=candidate_id,
                snapshot_stage="verified",
            )
            db.add(snap)

        snap.safety_score = scores["safetyScore"]
        snap.chat_score = scores["chatScore"]
        snap.second_date_score = scores["secondDateScore"]
        snap.conflict_risk_score = scores["conflictRiskScore"]
        snap.verify_count = candidate["unknownConstraintCount"]
        snap.final_rank_score = Decimal(str(score))
        snap.verify_pending_count = candidate["unknownConstraintCount"]
        snap.rank_change_reason = "verified_rerank"
        snap.explanation_json = {
            "reason": "verified_ranking",
            "sortScore": round(score, 2),
            "baseAverage": round(final_average, 2),
            "unknownConstraintCount": candidate["unknownConstraintCount"],
            "softPreferenceScore": float(candidate["softPreference"]["adjustment"]),
            "softPreferenceApplied": candidate["softPreference"]["applied"],
            "softPreferenceUnmet": candidate["softPreference"]["unmet"],
            "softPreferenceUnknown": candidate["softPreference"]["unknown"],
            "feedbackAdjustment": candidate["feedbackAdjustment"],
            "usedConfirmedVerifyTasks": used_confirmed_task_count,
        }
        snap.created_at = timestamp

        result_items.append(
            {
                "candidateId": candidate_id,
                "score": round(score, 2),
                "rank": rank,
            }
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not retry_on_conflict:
            raise
        return regenerate_candidates(
            db,
            requester_user_id=requester_user_id,
            top_n=top_n,
            retry_on_conflict=False,
        )

    return {
        "requesterId": requester_user_id,
        "stage": "verified",
        "usedConfirmedVerifyTasks": used_confirmed_task_count,
        "items": result_items,
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
