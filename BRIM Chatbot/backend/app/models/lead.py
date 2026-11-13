"""Sales leads captured by the conversation flow."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.base import Base


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CLOSED = "CLOSED"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False)
    email = Column(String(255), nullable=True)
    preferred_contact = Column(String(32), default="Phone", nullable=False)  # Phone / WhatsApp / Email
    # When the person is comfortable being contacted ("weekday evenings", "after 6pm", "anytime").
    # A callback list without this is a list of people who will be called at a bad time.
    preferred_time = Column(String(160), nullable=True)
    timezone = Column(String(64), nullable=True)
    requirements = Column(Text, nullable=True)
    intent = Column(String(32), nullable=True)  # buying / renting
    location = Column(String(255), nullable=True)
    budget_max = Column(Integer, nullable=True)
    meeting_requested = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default=LeadStatus.NEW.value, nullable=False, index=True)
    # chat | idle_prompt | mid_conversation | contact_form | scheduling | admin
    source = Column(String(64), default="chatbot", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", backref="leads")
    meetings = relationship("Meeting", back_populates="lead", cascade="all, delete-orphan")
