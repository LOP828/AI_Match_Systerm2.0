"""多头评分与粗排/精排"""

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import UserConstraint, UserProfile


def calculate_multi_scores(
    requester: UserProfile,
    candidate: UserProfile,
    requester_constraints: list[UserConstraint],
) -> dict[str, Decimal]:
    """
    计算多头评分：安全度、聊天顺畅度、二次见面概率、冲突风险
    返回值 0-100
    """
    safety = Decimal("85")  # 默认
    chat = Decimal("75")
    second_date = Decimal("70")
    conflict = Decimal("20")  # 冲突风险，越低越好

    # 安全度：有 block 约束且候选人不满足则已在 rule_engine 阻断，这里主要看 verify 数量
    verify_count = sum(1 for c in requester_constraints if c.tag_type == "verify")
    if verify_count > 0:
        safety = safety - Decimal(verify_count) * 5
    safety = max(Decimal("0"), min(Decimal("100"), safety))

    # 聊天顺畅度：年龄差、城市、学历匹配
    if requester.age and candidate.age:
        age_diff = abs(requester.age - candidate.age)
        if age_diff <= 3:
            chat += Decimal("10")
        elif age_diff <= 5:
            chat += Decimal("5")
        elif age_diff > 10:
            chat -= Decimal("10")
    if requester.city_code and candidate.city_code and requester.city_code == candidate.city_code:
        chat += Decimal("8")
    if requester.education_level and candidate.education_level:
        edu_order = ["high_school", "bachelor", "master", "phd"]
        try:
            r_idx = edu_order.index(requester.education_level)
            c_idx = edu_order.index(candidate.education_level)
            if abs(r_idx - c_idx) <= 1:
                chat += Decimal("5")
        except ValueError:
            pass
    chat = max(Decimal("0"), min(Decimal("100"), chat))

    # 二次见面概率：综合
    second_date = (safety + chat) / 2
    second_date = max(Decimal("0"), min(Decimal("100"), second_date))

    # 冲突风险：生活方式差异
    if requester.smoking_status and candidate.smoking_status:
        if requester.smoking_status != candidate.smoking_status:
            conflict += Decimal("15")
    if requester.pet_status and candidate.pet_status:
        if "has" in (requester.pet_status or "") and "no" in (candidate.pet_status or ""):
            conflict += Decimal("10")
    conflict = max(Decimal("0"), min(Decimal("100"), conflict))

    return {
        "safetyScore": safety,
        "chatScore": chat,
        "secondDateScore": second_date,
        "conflictRiskScore": conflict,
    }
