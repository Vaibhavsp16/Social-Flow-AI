"""
Platform activity log.

Events join the caller's transaction (add + flush, no commit) so an activity row and the action it
describes commit together. Call sites that do not otherwise write (login) commit explicitly.
Logging failures are swallowed: analytics must never break signup, publishing or a chat turn.
"""

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent

logger = logging.getLogger(__name__)


def log_activity(
    db: Session,
    event_type: str,
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Queue an event on the current transaction. Never raises."""
    try:
        db.add(
            ActivityEvent(
                user_id=user_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_json=json.dumps(metadata or {}),
            )
        )
        db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not record activity {event_type}: {exc}")
