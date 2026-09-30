from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base

class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(50), default="English", nullable=False)
    personality = Column(String(100), default="Friendly & professional", nullable=False)
    welcome_message = Column(Text, default="Hi! How can I help you today?", nullable=False)
    status = Column(String(50), default="Live", nullable=False)
    shareable_slug = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="bots")
    knowledge_sources = relationship("KnowledgeSource", back_populates="bot", cascade="all, delete-orphan")
    chunks = relationship("KnowledgeChunk", back_populates="bot", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="bot", cascade="all, delete-orphan")

