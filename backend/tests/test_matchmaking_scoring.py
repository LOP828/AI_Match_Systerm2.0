"""Tests for soft prefer/avoid matchmaking scoring."""

from sqlalchemy.orm import Session

from app.models import RecommendationSnapshot, UserPreference, UserProfile
from app.services.recommendation_service import generate_candidates


def _seed_base_profiles(db: Session) -> None:
    db.add_all(
        [
            UserProfile(
                user_id=1,
                gender="male",
                age=30,
                height_cm=175,
                city_code="SH",
                education_level="bachelor",
                marital_status="single",
                active_status="active",
                open_to_match=1,
            ),
            UserProfile(
                user_id=2,
                gender="female",
                age=28,
                city_code="SH",
                education_level="bachelor",
                marital_status="single",
                active_status="active",
                open_to_match=1,
            ),
            UserProfile(
                user_id=3,
                gender="female",
                age=28,
                city_code="SH",
                education_level="bachelor",
                marital_status="single",
                active_status="active",
                open_to_match=1,
            ),
        ]
    )
    db.commit()


def test_generate_candidates_rewards_soft_preference_matches(db_session: Session):
    _seed_base_profiles(db_session)
    candidate_match = db_session.query(UserProfile).filter(UserProfile.user_id == 2).first()
    candidate_other = db_session.query(UserProfile).filter(UserProfile.user_id == 3).first()
    candidate_match.height_cm = 170
    candidate_other.height_cm = 190
    db_session.add(
        UserPreference(
            user_id=1,
            dimension="height",
            operator="between",
            value_json={"min": 168, "max": 175},
            priority_level="prefer",
        )
    )
    db_session.commit()

    result = generate_candidates(db_session, requester_user_id=1)

    assert [item["candidateId"] for item in result["topCandidates"][:2]] == [2, 3]
    assert result["topCandidates"][0]["scores"]["chatScore"] > result["topCandidates"][1]["scores"]["chatScore"]

    snapshots = {
        row.candidate_user_id: row
        for row in db_session.query(RecommendationSnapshot)
        .filter(RecommendationSnapshot.requester_user_id == 1)
        .all()
    }
    preferred_snapshot = snapshots[2]
    other_snapshot = snapshots[3]
    assert preferred_snapshot.explanation_json["softPreferenceScore"] > other_snapshot.explanation_json["softPreferenceScore"]
    assert preferred_snapshot.explanation_json["softPreferenceApplied"][0]["priority"] == "prefer"


def test_generate_candidates_penalizes_avoid_hits_and_keeps_unknown_neutral(db_session: Session):
    _seed_base_profiles(db_session)
    candidate_unknown = db_session.query(UserProfile).filter(UserProfile.user_id == 2).first()
    candidate_avoid = db_session.query(UserProfile).filter(UserProfile.user_id == 3).first()
    candidate_unknown.height_cm = None
    candidate_avoid.height_cm = 190
    db_session.add(
        UserPreference(
            user_id=1,
            dimension="height",
            operator="between",
            value_json={"min": 185, "max": 195},
            priority_level="avoid",
        )
    )
    db_session.commit()

    result = generate_candidates(db_session, requester_user_id=1)

    assert [item["candidateId"] for item in result["topCandidates"][:2]] == [2, 3]

    snapshots = {
        row.candidate_user_id: row
        for row in db_session.query(RecommendationSnapshot)
        .filter(RecommendationSnapshot.requester_user_id == 1)
        .all()
    }
    neutral_snapshot = snapshots[2]
    penalized_snapshot = snapshots[3]
    assert neutral_snapshot.explanation_json["softPreferenceScore"] == 0.0
    assert len(neutral_snapshot.explanation_json["softPreferenceUnknown"]) == 1
    assert penalized_snapshot.explanation_json["softPreferenceScore"] < 0.0
    assert penalized_snapshot.explanation_json["softPreferenceApplied"][0]["priority"] == "avoid"
