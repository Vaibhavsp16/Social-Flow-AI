import json
import logging
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.embedding_service import EmbeddingService
from app.schemas.chat import SourceCitation

logger = logging.getLogger(__name__)

class RetrievalService:
    @staticmethod
    def search_relevant_chunks(
        db: Session,
        bot_id: int,
        query: str,
        top_k: int = 4,
        threshold: float = 0.05
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Semantic search filtering strictly on bot_id for multi-tenant isolation.
        Returns list of (KnowledgeChunk, similarity_score).
        """
        if not query or not query.strip():
            return []

        # 1. Embed query
        query_embedding = EmbeddingService.get_embedding(query)

        # 2. Retrieve chunks for THIS bot only
        chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.bot_id == bot_id)
            .all()
        )

        if not chunks:
            return []

        # 3. Compute cosine similarity for each chunk
        scored_chunks = []
        for chunk in chunks:
            if not chunk.embedding_json:
                continue
            try:
                chunk_vec = json.loads(chunk.embedding_json)
                score = EmbeddingService.cosine_similarity(query_embedding, chunk_vec)
                if score >= threshold:
                    scored_chunks.append((chunk, score))
            except Exception as e:
                logger.warning(f"Failed to parse embedding for chunk {chunk.id}: {e}")

        # 4. Sort descending by score and take top_k
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

    @staticmethod
    def format_citations(scored_chunks: List[Tuple[KnowledgeChunk, float]]) -> List[SourceCitation]:
        """
        Convert retrieved chunk tuples into structured SourceCitation models.
        """
        citations = []
        for chunk, score in scored_chunks:
            snippet = chunk.content[:280] + ("..." if len(chunk.content) > 280 else "")
            citations.append(
                SourceCitation(
                    source_id=chunk.knowledge_source_id,
                    source_name=chunk.source_name,
                    source_type=chunk.source_type,
                    source_url=chunk.source_url,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    similarity_score=round(score, 4),
                    snippet=snippet,
                )
            )
        return citations
