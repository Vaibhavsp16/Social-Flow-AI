from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.core.constants import KnowledgeSourceType, ProcessingStatus

class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    source_url = Column(String(1000), nullable=True)
    processing_status = Column(String(50), default=ProcessingStatus.UPLOADED.value, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    chunks_count = Column(Integer, default=0, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", back_populates="knowledge_sources")
    chunks = relationship("KnowledgeChunk", back_populates="knowledge_source", cascade="all, delete-orphan")
