import json
import logging
import math
import os
import re
from typing import Dict, List, Tuple, Optional
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
        """
        Broad-exploratory detection, shared with the LLM service.

        A keyword set used to live here and treated any question containing "available" or
        "service" as an overview request, which returned arbitrary leading chunks instead of
        refusing when nothing matched ("what amenities are available at Harbour View Villas?").
        """
        from app.services.llm_service import LLMService

        return LLMService.is_overview_query(query)

    @staticmethod
    def _overview_fallback(chunks: List[KnowledgeChunk], top_k: int) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Leading chunks for a broad exploratory question.

        Scoped to the current bot and drawn only from real stored chunks, so the assistant can
        describe the knowledge it actually holds instead of refusing.
        """
        ordered = sorted(chunks, key=lambda c: (c.knowledge_source_id, c.chunk_index))
        return [(c, 0.0) for c in ordered[:top_k]]

    # Cosine similarity scales differ by provider, so the relevance cut-off has to as well.
    # Measured on BRIM industry content: relevant questions score 0.31-0.75 with OpenAI vectors
    # while unrelated ones stay at or below 0.11; the local hashing projection produces much
    # smaller absolute scores.
    # 0.20 keeps unrelated questions out (measured at or below 0.11) while not rejecting
    # paraphrases of short OCR'd passages, which sat at 0.21-0.24.
    DEFAULT_THRESHOLD_OPENAI = 0.18
    # Measured on the demo corpus with local embeddings: genuine questions score 0.19-0.46,
    # an unrelated "starship warranty" question 0.078. The old 0.02 let that through and the
    # bot answered from an unrelated policy document instead of refusing.
    DEFAULT_THRESHOLD_LOCAL = 0.12

    @classmethod
    def default_threshold(cls, provider: str) -> float:
        if provider == EmbeddingService.PROVIDER_OPENAI:
            return cls.DEFAULT_THRESHOLD_OPENAI
        return cls.DEFAULT_THRESHOLD_LOCAL

    @staticmethod
    def _search_vector(
        db: Session,
        bot_id: int,
        query: str,
        top_k: int = 4,
        threshold: Optional[float] = None
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

        # The OpenAI call can fail transiently and degrade to the local engine. Comparing a
        # local query vector against OpenAI chunk vectors returns nothing, which surfaced as a
        # refusal even though the knowledge was there. Detect that mismatch and answer
        # lexically instead of claiming the bot knows nothing.
        # Vectors from different providers are not comparable. A provider outage can leave a
        # bot's chunks embedded locally while a later query succeeds on OpenAI (or the reverse),
        # so check what this bot actually holds before trusting the vector search.
        stored_providers = {
            (row[0] or EmbeddingService.PROVIDER_LOCAL)
            for row in db.query(KnowledgeChunk.embedding_provider)
            .filter(KnowledgeChunk.bot_id == bot_id)
            .distinct()
            .all()
        }
        if stored_providers and provider not in stored_providers:
            logger.warning(
                "Provider mismatch (query=%s, stored=%s); using lexical search",
                provider, sorted(stored_providers),
            )
            return RetrievalService._lexical_search(db, bot_id, query, top_k)

        if provider == EmbeddingService.PROVIDER_LOCAL:
            # The local "embedding" is a hashing projection; cosine over it is noisy (related
            # sentences can score near zero). Keyword overlap over the bot's own chunks is the
            # honest retrieval mode when no embedding provider is reachable.
            logger.info("Local embedding provider active; using lexical retrieval")
            return RetrievalService._lexical_search(db, bot_id, query, top_k)

        if threshold is None:
            threshold = RetrievalService.default_threshold(provider)

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

    STOPWORDS = {
        "the", "and", "for", "with", "what", "which", "does", "did", "are", "was", "were",
        "how", "when", "where", "who", "why", "can", "could", "you", "your", "our", "this",
        "that", "there", "have", "has", "had", "from", "about", "into", "will", "would",
        "tell", "give", "please", "know", "want", "need", "any", "all", "some", "more",
        # Devanagari / Gujarati function words, so Hindi and Gujarati queries keep their
        # content words rather than scoring every chunk equally.
        "क्या", "कौन", "कब", "कहाँ", "कहां", "कैसे", "है", "हैं", "का", "की", "के", "को",
        "में", "से", "और", "यह", "वह", "कि", "पर", "हो", "था", "थी",
        "શું", "કોણ", "ક્યારે", "ક્યાં", "કેવી", "છે", "છો", "નો", "ની", "ને", "માં", "થી",
        "અને", "આ", "તે", "કે", "પર", "હતું",
    }

    # Word boundary that also covers Devanagari and Gujarati, which [a-z] silently skipped:
    # lexical search used to return nothing at all for a Hindi or Gujarati question.
    TOKEN_PATTERN = re.compile(
        r"[a-z0-9]{3,}|[\u0900-\u097F\u0A80-\u0AFF\u0C00-\u0C7F]{2,}",
        re.IGNORECASE,
    )

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return [token.lower() for token in RetrievalService.TOKEN_PATTERN.findall(text or "")]

    @staticmethod
    def search_relevant_chunks(
        db: Session,
        bot_id: int,
        query: str,
        top_k: int = 6,
        threshold: Optional[float] = None,
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Hybrid retrieval: vector similarity plus keyword overlap, merged per chunk.

        Embeddings are strong on paraphrase and weak on entity names, numbers and project
        names; keyword matching is the reverse. Keeping the better score for each chunk stops
        answers drifting to a loosely related source — the failure behind "it answers something
        else".
        """
        vector_hits = RetrievalService._search_vector(db, bot_id, query, top_k, threshold)
        lexical_hits = RetrievalService._lexical_search(db, bot_id, query, top_k)

        merged: Dict[int, Tuple[KnowledgeChunk, float]] = {}
        for chunk, score in lexical_hits:
            merged[chunk.id] = (chunk, round(float(score), 4))
        for chunk, score in vector_hits:
            previous = merged.get(chunk.id)
            if previous is None or score > previous[1]:
                merged[chunk.id] = (chunk, round(float(score), 4))

        ranked = sorted(merged.values(), key=lambda item: item[1], reverse=True)
        return ranked[:top_k]

    @staticmethod
    def _lexical_search(
        db: Session, bot_id: int, query: str, top_k: int = 6
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        IDF-weighted keyword matching over the bot's own chunks.

        A flat overlap ratio treated "company" (in every brochure page) the same as "developer"
        (in one), which pulled whole unrelated sections into the answer. Weighting each query
        term by how rare it is within this bot keeps the distinctive words — project names,
        numbers, "developer" — in control.
        """
        query_terms = {
            term for term in RetrievalService._tokens(query)
            if term not in RetrievalService.STOPWORDS
        }
        if not query_terms:
            return []

        chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.bot_id == bot_id).all()
        if not chunks:
            return []

        doc_terms: List[set] = []
        document_frequency: Dict[str, int] = {}
        for chunk in chunks:
            terms = set(RetrievalService._tokens(chunk.content or ""))
            doc_terms.append(terms)
            for term in terms & query_terms:
                document_frequency[term] = document_frequency.get(term, 0) + 1

        if not document_frequency:
            return []

        total_docs = len(chunks)

        def idf(term: str) -> float:
            return math.log(1 + total_docs / (1 + document_frequency.get(term, 0)))

        denominator = sum(idf(term) for term in query_terms) or 1.0

        scored: List[Tuple[KnowledgeChunk, float]] = []
        for chunk, terms in zip(chunks, doc_terms):
            matched = query_terms & terms
            if not matched:
                # Simple stemming: "developer" should find "developers", "floors" → "floor".
                for term in query_terms:
                    if len(term) >= 5 and any(
                        word.startswith(term[:5]) for word in terms
                    ):
                        matched = matched | {term}
            if not matched:
                continue
            score = sum(idf(term) for term in matched) / denominator
            # One distinctive term is enough; several weak ones are not.
            if score >= 0.15 or len(matched) >= 2:
                scored.append((chunk, round(min(score, 0.95), 4)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _apply_relevance_gate(
        scored_chunks: List[Tuple[KnowledgeChunk, float]],
        top_k: int,
        threshold: float,
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Keep only chunks that clear the similarity threshold.

        Nothing above the threshold means the knowledge base does not contain the answer; an
        empty result is correct there because it produces a grounded refusal. Returning the
        best-scoring chunk regardless ("always return something") made unrelated questions look
        grounded, which is the failure mode this gate exists to prevent.
        """
        return [(c, s) for c, s in scored_chunks if s >= threshold][:top_k]

    # The answer is written from the full retrieved set, but a reader only needs the passages the
    # answer actually rests on. Listing eight chips under a two-sentence reply buries the useful
    # one, so the display set is capped.
    MAX_DISPLAY_CITATIONS = 4
    MIN_DISPLAY_SCORE = 0.20

    @classmethod
    def display_citations(
        cls, scored_chunks: List[Tuple[KnowledgeChunk, float]]
    ) -> List[Tuple[KnowledgeChunk, float]]:
        if not scored_chunks:
            return []
        strong = [(chunk, score) for chunk, score in scored_chunks if score >= cls.MIN_DISPLAY_SCORE]
        # Never show nothing when an answer was produced from something.
        return (strong or scored_chunks[:1])[: cls.MAX_DISPLAY_CITATIONS]

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
