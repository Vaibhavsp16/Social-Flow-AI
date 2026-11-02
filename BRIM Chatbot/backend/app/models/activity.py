"""Append-only platform activity log used by the admin activity view."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.base import Base


class ActivityType(str, enum.Enum):
    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    PROJECT_CREATED = "project_created"
    BOT_CREATED = "bot_created"
    BOT_PUBLISHED = "bot_published"
    KNOWLEDGE_ADDED = "knowledge_added"
    CONVERSATION_STARTED = "conversation_started"
    LEAD_CAPTURED = "lead_captured"
    HANDOFF_REQUESTED = "handoff_requested"


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Nullable so public widget events (conversation started) still record an actor-less event.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(Integer, nullable=True)
    # Deliberately small and non-sensitive: ids, names, counts. Never emails or phone numbers.
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
