"""Meetings the bot arranged on the business's behalf.

A meeting is a separate record from a lead: one person can book a site visit and later ask for a
callback, and the business needs to see both. The bot stores the slot the visitor *asked for* even
when nobody has confirmed it yet, because "call me Tuesday evening" is the whole value of the
request — the confirmation happens outside the chat.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.base import Base


class MeetingStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MeetingMode(str, enum.Enum):
    CALL = "call"
    VISIT = "visit"
    VIDEO = "video"
    OFFICE = "office"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name = Column(String(120), nullable=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(255), nullable=True)
    mode = Column(String(16), default=MeetingMode.CALL.value, nullable=False)
    # Free text as the visitor phrased it: "Tuesday evening", "this weekend", "after 6pm".
    preferred_slot = Column(String(200), nullable=True)
    # Resolved datetime when the phrase maps to a concrete slot; NULL means "team will confirm".
    scheduled_for = Column(DateTime, nullable=True)
    timezone = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default=MeetingStatus.REQUESTED.value, nullable=False, index=True)
    source = Column(String(64), default="chatbot", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", back_populates="meetings")
    lead = relationship("Lead", back_populates="meetings")
    conversation = relationship("Conversation", back_populates="meetings")
