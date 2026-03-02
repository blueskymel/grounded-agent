import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("groundedagent")


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    # One-line JSON logs (App Insights friendly later)
    logger.info(json.dumps(payload, ensure_ascii=False))