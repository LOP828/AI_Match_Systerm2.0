import json
import logging
from typing import Any


def configure_application_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _normalize_detail(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _normalize_detail(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_detail(item) for item in value]
    return str(value)


def audit_log(
    event_type: str,
    outcome: str,
    actor: Any = None,
    request: Any = None,
    **details: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": event_type,
        "outcome": outcome,
    }

    if actor is not None:
        payload["actorUserId"] = getattr(actor, "user_id", None)
        payload["actorRole"] = getattr(actor, "role", None)
        payload["actorSource"] = getattr(actor, "source", None)

    if request is not None:
        payload["path"] = getattr(getattr(request, "url", None), "path", None)
        payload["method"] = getattr(request, "method", None)
        payload["clientIp"] = getattr(getattr(request, "client", None), "host", None)

    for key, value in details.items():
        payload[key] = _normalize_detail(value)

    logging.getLogger("app.audit").info("audit %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))