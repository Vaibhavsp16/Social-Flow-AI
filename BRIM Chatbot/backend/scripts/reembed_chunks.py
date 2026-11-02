"""
Re-embed stored chunks with the currently active embedding provider.

Run from backend/:  python scripts/reembed_chunks.py [--all]

Retrieval only compares vectors produced by the same provider, so chunks embedded before an
OpenAI key was configured are invisible once OpenAI embeddings are active (and vice versa after
switching EMBEDDING_PROVIDER to local). This rewrites those vectors in place.

Without --all only chunks whose provider differs from the active one are rewritten.
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.database.session import SessionLocal  # noqa: E402
from app.models.knowledge_chunk import KnowledgeChunk  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402


def main() -> int:
    force_all = "--all" in sys.argv[1:]
    active = EmbeddingService.active_provider()
    print(f"Active embedding provider: {active}")

    db = SessionLocal()
    try:
        chunks = db.query(KnowledgeChunk).all()
        targets = [
            chunk for chunk in chunks
            if force_all or (chunk.embedding_provider or EmbeddingService.PROVIDER_LOCAL) != active
        ]
        print(f"{len(chunks)} chunks total, {len(targets)} to re-embed")

        rewritten = 0
        for chunk in targets:
            vector, provider = EmbeddingService.get_embedding_with_provider(chunk.content)
            if provider != active:
                print(f"Stopped: embedding provider degraded to {provider} (check the API key/quota).")
                break
            chunk.embedding_vector = vector
            chunk.embedding_provider = provider
            rewritten += 1
            if rewritten % 50 == 0:
                db.commit()
                print(f"  ... {rewritten}")

        db.commit()
        print(f"Re-embedded {rewritten} chunks with provider '{active}'.")
        return 0 if rewritten == len(targets) else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
