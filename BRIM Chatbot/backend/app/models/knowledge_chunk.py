from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database.base import Base

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_source_id = Column(Integer, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(String(1000), nullable=True)
    page_number = Column(String(50), nullable=True)
    metadata_json = Column(Text, default="{}", nullable=False)
    embedding_json = Column(Text, nullable=True)  # JSON-serialized embedding vector (1536 dim)
    embedding_vector = Column(Vector(1536), nullable=True)  # Native pgvector 1536-dim vector
    # Which provider produced embedding_vector ('openai' or 'local'). Vectors from different
    # providers are not comparable, so retrieval only scores chunks from the matching provider.
    # NULL is treated as 'local' for rows created before this column existed.
    embedding_provider = Column(String(20), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", back_populates="chunks")
    knowledge_source = relationship("KnowledgeSource", back_populates="chunks")
