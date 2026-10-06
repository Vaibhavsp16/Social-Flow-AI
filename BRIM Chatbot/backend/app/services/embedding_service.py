import os
import re
import math
import time
import hashlib
import logging
from collections import Counter
from typing import List, Tuple
import numpy as np
import httpx

logger = logging.getLogger(__name__)

PROVIDER_OPENAI = "openai"
PROVIDER_LOCAL = "local"

# Common English function words. Removing them before hashing keeps the vector focused on the
# content-bearing terms, which materially improves ranking for the local projection.
STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "yours", "with", "about", "this",
    "that", "these", "those", "from", "have", "has", "had", "was", "were", "will", "would",
    "can", "could", "should", "does", "did", "doing", "what", "which", "where", "when", "who",
    "whom", "why", "how", "all", "any", "some", "each", "other", "into", "out", "our", "ours",
    "their", "them", "they", "his", "her", "she", "him", "its", "it's", "there", "here", "then",
    "than", "too", "very", "just", "also", "get", "got", "been", "being", "more", "most", "much",
    "many", "such", "only", "own", "same", "so", "up", "down", "off", "over", "under", "again",
    "please", "tell", "give", "want", "need", "know", "like", "let", "make", "made", "use",
    "used", "using", "see", "say", "said", "one", "two", "may", "might", "must", "shall",
}


class EmbeddingService:
    DIMENSION = 1536

    _openai_quota_exhausted: bool = False
    _openai_last_checked: float = 0.0

    # ── Provider selection ────────────────────────────────────────────────────

    @classmethod
    def active_provider(cls) -> str:
        """
        The provider that would be used right now, without performing a call.

        Used to decide which stored vectors are comparable with a freshly embedded query.
        """
        key = os.getenv("OPENAI_API_KEY") or ""
        if (
            key.startswith("sk-")
            and len(key) > 20
            and not cls._openai_quota_exhausted
        ):
            return PROVIDER_OPENAI
        return PROVIDER_LOCAL

    @classmethod
    def get_embedding_with_provider(cls, text: str) -> Tuple[List[float], str]:
        """
        Generate an embedding and report which provider produced it.

        Vectors from different providers live in unrelated spaces and must never be compared,
        so callers persist the provider alongside the vector.
        """
        if not text or not text.strip():
            return [0.0] * cls.DIMENSION, PROVIDER_LOCAL

        openai_key = os.getenv("OPENAI_API_KEY")
        now = time.time()
        if (
            openai_key
            and openai_key.startswith("sk-")
            and len(openai_key) > 20
            and (not cls._openai_quota_exhausted or now - cls._openai_last_checked > 300)
        ):
            try:
                with httpx.Client(timeout=8.0) as client:
                    response = client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        json={
                            "input": text[:8000],
                            "model": "text-embedding-3-small",
                        },
                    )
                    cls._openai_last_checked = now
                    if response.status_code == 200:
                        data = response.json()
                        cls._openai_quota_exhausted = False
                        return data["data"][0]["embedding"], PROVIDER_OPENAI

                    if response.status_code in (429, 401):
                        cls._openai_quota_exhausted = True
                        logger.warning(
                            "OpenAI embeddings unavailable (status %s). Using the local "
                            "deterministic projection for this process.",
                            response.status_code,
                        )
                    else:
                        logger.warning(
                            "OpenAI embedding call returned status %s, using local engine",
                            response.status_code,
                        )
            except Exception as e:
                logger.warning(f"OpenAI embedding call failed ({e}), using local engine")

        return cls._generate_local_embedding(text), PROVIDER_LOCAL

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        """Backwards-compatible accessor returning just the vector."""
        return cls.get_embedding_with_provider(text)[0]

    # ── Local deterministic projection ────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Lowercase, strip punctuation and drop stop words/short tokens.

        Punctuation matters: without it "Palms?" and "Palms" hash to different buckets and
        relevant chunks get missed.
        """
        words = re.findall(r"[a-z0-9]+", text.lower())
        content = [w for w in words if len(w) > 2 and w not in STOP_WORDS]
        # Very short or stopword-only inputs still need a usable vector.
        return content or [w for w in words if len(w) > 1]

    @staticmethod
    def _generate_local_embedding(text: str) -> List[float]:
        """
        Deterministic, dependency-free semantic projection.

        Not a learned model, but a considerably better lexical signal than plain bag-of-words:
        punctuation-insensitive tokens, stop-word removal, sublinear term weighting (so a
        repeated word cannot dominate), word bigrams for phrase matching, and character
        n-grams for morphological robustness. Every feature is hash-projected into a dense,
        unit-normalised 1536-dimensional vector.
        """
        dim = EmbeddingService.DIMENSION
        vector = np.zeros(dim, dtype=np.float32)

        tokens = EmbeddingService._tokenize(text)
        if not tokens:
            return vector.tolist()

        # Term frequency with sublinear scaling
        for term, count in Counter(tokens).items():
            h = int(hashlib.sha256(term.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vector[idx] += sign * (1.0 + math.log(count))

            # Character 4-grams: lower weight, helps with plurals/typos.
            if len(term) >= 4:
                for j in range(len(term) - 3):
                    ngram = term[j:j + 4]
                    nh = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
                    n_idx = nh % dim
                    n_sign = 1.0 if (nh >> 4) % 2 == 0 else -1.0
                    vector[n_idx] += n_sign * 0.25

        # Word bigrams capture short phrases ("sunset palms", "site visit").
        for a, b in zip(tokens, tokens[1:]):
            bh = int(hashlib.sha256(f"{a}_{b}".encode("utf-8")).hexdigest(), 16)
            b_idx = bh % dim
            b_sign = 1.0 if (bh >> 6) % 2 == 0 else -1.0
            vector[b_idx] += b_sign * 0.6

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        sim = float(np.dot(a, b) / (norm_a * norm_b))
        return max(0.0, min(1.0, sim))
