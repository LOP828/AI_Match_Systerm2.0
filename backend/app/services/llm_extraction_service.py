import json
import logging
from decimal import Decimal

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AiExtraction, InteractionMemo

logger = logging.getLogger(__name__)
MODEL_NAME = "deepseek-chat"

EXTRACTION_PROMPT = """You are a professional matchmaking assistant. Extract from the memo below:
1. Observation tags: positive or neutral descriptions about personality, communication style, or values.
2. Risk hints: potential issues or concerns that deserve follow-up.

Memo:
---
{memo_text}
---

Return JSON only in this format:
{{
  "observation_tags": [{{"tag_code": "code", "tag_value": "value", "confidence": 0, "evidence": "reason"}}],
  "risk_hints": [{{"label": "risk", "confidence": 0, "evidence": "reason"}}]
}}
"""


def _get_client() -> OpenAI | None:
    settings = get_settings()
    if not settings.ai_extraction_enabled or not settings.deepseek_api_key:
        return None
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
    )


def _extract_json_text(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return text


def _persist_failure(db: Session, memo_id: int, reason: str, detail: str) -> None:
    try:
        db.rollback()
        failure = AiExtraction(
            entity_type="memo",
            entity_id=memo_id,
            extracted_label=reason,
            extracted_value=reason,
            confidence=Decimal("0"),
            evidence_text=(detail or reason)[:1000],
            model_version=MODEL_NAME,
            extraction_status="failed",
        )
        db.add(failure)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed to persist extraction failure", extra={"memo_id": memo_id})


def extract_from_memo(db: Session, memo_id: int) -> list[AiExtraction]:
    """Extract observation tags and risk hints from a memo into ai_extraction rows."""
    memo = db.query(InteractionMemo).filter(InteractionMemo.memo_id == memo_id).first()
    if not memo or not memo.raw_text:
        return []

    client = _get_client()
    if not client:
        logger.warning("deepseek client unavailable; skipping extraction", extra={"memo_id": memo_id})
        _persist_failure(db, memo_id, "config_error", "AI extraction is disabled or DEEPSEEK_API_KEY is missing")
        return []

    prompt = EXTRACTION_PROMPT.format(memo_text=memo.raw_text[:2000])
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content if resp.choices else ""
    except Exception as exc:
        logger.exception("memo extraction request failed", extra={"memo_id": memo_id})
        _persist_failure(db, memo_id, "request_error", str(exc))
        return []

    content = _extract_json_text(content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("memo extraction returned non-json", extra={"memo_id": memo_id, "content_preview": content[:200]})
        _persist_failure(db, memo_id, "parse_error", f"{exc}: {content[:800]}")
        return []

    extractions: list[AiExtraction] = []
    try:
        for item in data.get("observation_tags") or []:
            ext = AiExtraction(
                entity_type="memo",
                entity_id=memo_id,
                extracted_label=item.get("tag_code") or item.get("tag_value") or "observation",
                extracted_value=item.get("tag_value"),
                confidence=Decimal(str(item.get("confidence", 80))),
                evidence_text=item.get("evidence"),
                model_version=MODEL_NAME,
                extraction_status="suggested",
            )
            db.add(ext)
            db.flush()
            extractions.append(ext)

        for item in data.get("risk_hints") or []:
            ext = AiExtraction(
                entity_type="memo",
                entity_id=memo_id,
                extracted_label=item.get("label") or "risk_hint",
                extracted_value=item.get("label"),
                confidence=Decimal(str(item.get("confidence", 70))),
                evidence_text=item.get("evidence"),
                model_version=MODEL_NAME,
                extraction_status="suggested",
            )
            db.add(ext)
            db.flush()
            extractions.append(ext)

        db.commit()
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        logger.exception("memo extraction payload invalid", extra={"memo_id": memo_id})
        _persist_failure(db, memo_id, "payload_error", str(exc))
        return []

    return extractions
