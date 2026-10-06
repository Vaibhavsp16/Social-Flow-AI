import json
import logging
import re
from typing import List, Tuple, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.embedding_service import EmbeddingService
from app.schemas.chat import SourceCitation

logger = logging.getLogger(__name__)


def _chunk_provider(chunk: KnowledgeChunk) -> str:
    """Provider a stored chunk was embedded with. Legacy rows (NULL) were local."""
    return getattr(chunk, "embedding_provider", None) or EmbeddingService.PROVIDER_LOCAL


def _provider_filter(provider: str):
    """
    SQL filter matching only chunks embedded by the same provider as the query.

    Comparing vectors produced by different providers yields meaningless similarities, so
    mismatched chunks are excluded rather than allowed to pollute the ranking.
    """
    if provider == EmbeddingService.PROVIDER_LOCAL:
        return or_(
            KnowledgeChunk.embedding_provider == provider,
            KnowledgeChunk.embedding_provider.is_(None),
        )
    return KnowledgeChunk.embedding_provider == provider


def _chunk_vector(chunk: KnowledgeChunk) -> Optional[List[float]]:
    """
    Return a chunk's stored embedding as a plain float list.

    Prefers the native pgvector column and falls back to the JSON copy, which is what is
    available when the app runs on SQLite.
    """
    raw = getattr(chunk, "embedding_vector", None)
    if raw is not None:
        try:
            vec = [float(x) for x in raw] if not isinstance(raw, str) else json.loads(raw)
            if vec:
                return vec
        except Exception:
            pass

    if chunk.embedding_json:
        try:
            vec = json.loads(chunk.embedding_json)
            if vec:
                return [float(x) for x in vec]
        except Exception:
            pass

    return None


class RetrievalService:
    # Words that signal a broad "what do you know about this business?" question rather than a
    # question about a specific fact.
    OVERVIEW_TERMS = {
        "information", "info", "about", "business", "company", "service", "services",
        "offer", "offers", "know", "knowledge", "overview", "summary", "details",
        "available", "help", "assist", "product", "products",
    }

    @staticmethod
    def _is_overview_query(query: str) -> bool:
        words = set(re.findall(r"[a-z0-9]+", (query or "").lower()))
        return bool(words & RetrievalService.OVERVIEW_TERMS)

    @staticmethod
    def _overview_fallback(chunks: List[KnowledgeChunk], top_k: int) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Leading chunks for a broad exploratory question.

        Scoped to the current bot and drawn only from real stored chunks, so the assistant can
        describe the knowledge it actually holds instead of refusing.
        """
        ordered = sorted(chunks, key=lambda c: (c.knowledge_source_id, c.chunk_index))
        return [(c, 0.0) for c in ordered[:top_k]]

    @staticmethod
    def search_relevant_chunks(
        db: Session,
        bot_id: int,
        query: str,
        top_k: int = 4,
        threshold: float = 0.02
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Semantic search filtered strictly on bot_id for multi-tenant isolation.
        Uses pgvector cosine distance on PostgreSQL, with an in-memory cosine fallback.
        Returns a list of (KnowledgeChunk, similarity_score).
        """
        if not query or not query.strip():
            return []

        # 1. Embed the query, recording which provider produced the vector
        query_embedding, provider = EmbeddingService.get_embedding_with_provider(query)

        # 2. Native pgvector search (PostgreSQL only)
        try:
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                pg_results = (
                    db.query(
                        KnowledgeChunk,
                        (1 - KnowledgeChunk.embedding_vector.cosine_distance(query_embedding)).label("score")
                    )
                    .filter(KnowledgeChunk.bot_id == bot_id)
                    .filter(KnowledgeChunk.embedding_vector.isnot(None))
                    .filter(_provider_filter(provider))
                    .order_by(KnowledgeChunk.embedding_vector.cosine_distance(query_embedding))
                    .limit(top_k)
                    .all()
                )
                scored = [(chunk, float(score)) for chunk, score in pg_results]
                if scored:
                    logger.debug(
                        f"pgvector search bot_id={bot_id}: top score {scored[0][1]:.4f} "
                        f"over {len(scored)} candidate(s)"
                    )
                    gated = RetrievalService._apply_relevance_gate(scored, top_k, threshold)
                    if gated:
                        return gated
                    # Nothing cleared the gate; fall through so a broad exploratory question can
                    # still be answered from the bot's own leading chunks.
        except Exception as e:
            logger.warning(f"Native pgvector search failed, using in-memory scoring: {e}")

        # 3. In-memory cosine scoring (SQLite, or pgvector unavailable)
        chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.bot_id == bot_id)
            .all()
        )
        # Only compare vectors produced by the same provider as the query.
        chunks = [c for c in chunks if _chunk_provider(c) == provider]
        if not chunks:
            return []

        scored_chunks: List[Tuple[KnowledgeChunk, float]] = []
        for chunk in chunks:
            chunk_vec = _chunk_vector(chunk)
            if not chunk_vec:
                continue
            try:
                score = EmbeddingService.cosine_similarity(query_embedding, chunk_vec)
            except Exception as e:
                logger.warning(f"Failed to score chunk {chunk.id}: {e}")
                continue
            scored_chunks.append((chunk, score))

        if not scored_chunks:
            return []

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        gated = RetrievalService._apply_relevance_gate(scored_chunks, top_k, threshold)
        if gated:
            return gated

        if RetrievalService._is_overview_query(query):
            return RetrievalService._overview_fallback(chunks, top_k)

        return []

    @staticmethod
    def _apply_relevance_gate(
        scored_chunks: List[Tuple[KnowledgeChunk, float]],
        top_k: int,
        threshold: float,
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Keep chunks that clear the similarity threshold.

        If nothing clears it, return the single best chunk only when it carries a genuinely
        positive signal — otherwise return nothing, so the assistant produces a grounded
        refusal instead of answering from an unrelated chunk.
        """
        above_threshold = [(c, s) for c, s in scored_chunks if s >= threshold]
        if above_threshold:
            return above_threshold[:top_k]

        if scored_chunks and scored_chunks[0][1] > 0.0:
            return [scored_chunks[0]]
        return []

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
