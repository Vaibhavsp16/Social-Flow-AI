"""Sales leads captured by the conversation flow."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
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
    requirements = Column(Text, nullable=True)
    intent = Column(String(32), nullable=True)  # buying / renting
    location = Column(String(255), nullable=True)
    budget_max = Column(Integer, nullable=True)
    status = Column(String(32), default=LeadStatus.NEW.value, nullable=False, index=True)
    source = Column(String(64), default="chatbot", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", backref="leads")
