from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.base import Base
import enum


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    HANDOFF_REQUESTED = "HANDOFF_REQUESTED"
    HANDED_OFF = "HANDED_OFF"


class MessageSender(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(128), nullable=False, index=True)
    intent = Column(String(100), nullable=True, default="browsing")
    status = Column(String(50), default=ConversationStatus.ACTIVE.value, nullable=False, index=True)
    # JSON blob: {"intent": "buying", "location": "Ambli", "bhk": 3, ...}
    conversation_state = Column(Text, default="{}", nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime, nullable=True)

    bot = relationship("Bot", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.timestamp")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(20), nullable=False)  # USER / ASSISTANT / SYSTEM
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    metadata_json = Column(Text, default="{}", nullable=False)  # sources, confidence, intent, etc.

    conversation = relationship("Conversation", back_populates="messages")
