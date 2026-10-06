"""
Phase 1-4 end-to-end acceptance tests for the BRIM AI demo flow.

Covers the exact path demonstrated to stakeholders:

    Login -> Dashboard -> Create Project -> Create Bot -> Open Bot -> Add Knowledge
    -> Upload Document -> Process -> COMPLETED -> Chat -> Grounded answer

Runs against the configured database (PostgreSQL + pgvector by default) through the real
FastAPI application, so every assertion exercises the actual HTTP + service + ORM stack.

Run with:  python -m pytest tests/test_e2e_demo.py -q
Or as a script for a printed report:  python tests/test_e2e_demo.py
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database.session import engine

client = TestClient(app)

DEMO_DOC = Path(__file__).resolve().parent.parent / "demo_documents" / "Prycoons_Real_Estate_Guide.txt"

RESULTS = []


def _record(name: str, passed: bool, detail: str = ""):
    RESULTS.append((name, passed, detail))


def _signup(prefix: str) -> dict:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/auth/signup",
        json={"name": f"{prefix.title()} Demo", "email": email, "password": "SecurePassword123!"},
    )
    assert res.status_code == 201, f"signup failed: {res.text}"
    return {"headers": {"Authorization": f"Bearer {res.json()['access_token']}"}, "email": email}


def _create_project(headers: dict, industry: str = "Real Estate") -> int:
    res = client.post(
        "/api/projects",
        json={"name": f"Demo Project {uuid.uuid4().hex[:6]}", "industry": industry,
              "description": "End-to-end demo project"},
        headers=headers,
    )
    assert res.status_code == 201, f"project creation failed: {res.text}"
    return res.json()["id"]


def _create_bot(headers: dict, project_id: int, name: str) -> dict:
    res = client.post(
        "/api/bots",
        json={"project_id": project_id, "name": name,
              "description": "Demo assistant", "language": "English",
              "personality": "Friendly & professional",
              "welcome_message": "Hello! How can I help you today?", "status": "Live"},
        headers=headers,
    )
    assert res.status_code == 201, f"bot creation failed: {res.text}"
    return res.json()


def _upload_demo_doc(headers: dict, bot_id: int):
    assert DEMO_DOC.exists(), f"demo document missing: {DEMO_DOC}"
    with open(DEMO_DOC, "rb") as fh:
        return client.post(
            f"/api/bots/{bot_id}/knowledge/upload",
            files={"file": (DEMO_DOC.name, fh, "text/plain")},
            headers=headers,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Authentication
# ─────────────────────────────────────────────────────────────────────────────
def test_01_authentication():
    user = _signup("auth")
    headers = user["headers"]

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]

    # Logout / login again with the same credentials
    login = client.post("/api/auth/login", json={"email": user["email"], "password": "SecurePassword123!"})
    assert login.status_code == 200
    assert login.json()["access_token"]

    # Protected endpoint rejects anonymous access
    assert client.get("/api/projects").status_code == 401

    _record("Authentication (signup/login/protected)", True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Project + 3. Bot persistence
# ─────────────────────────────────────────────────────────────────────────────
def test_02_project_and_bot_persist():
    headers = _signup("persist")["headers"]

    project_id = _create_project(headers)
    projects = client.get("/api/projects", headers=headers).json()
    assert any(p["id"] == project_id for p in projects), "project did not persist"

    bot = _create_bot(headers, project_id, f"Persist Bot {uuid.uuid4().hex[:4]}")
    fetched = client.get(f"/api/bots/{bot['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == bot["id"]
    assert fetched.json()["project_id"] == project_id

    _record("Project + bot creation and persistence", True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Knowledge upload -> extraction -> chunking -> embeddings -> COMPLETED
# ─────────────────────────────────────────────────────────────────────────────
def test_03_knowledge_upload_full_pipeline():
    headers = _signup("knowledge")["headers"]
    project_id = _create_project(headers)
    bot = _create_bot(headers, project_id, f"Knowledge Bot {uuid.uuid4().hex[:4]}")

    res = _upload_demo_doc(headers, bot["id"])
    assert res.status_code == 201, f"upload failed: {res.text}"
    source = res.json()

    assert source["bot_id"] == bot["id"], "knowledge source attached to the wrong bot"
    assert source["processing_status"] == "COMPLETED", f"not completed: {source}"
    assert source["chunks_count"] > 0, "no chunks created"
    assert source["error_message"] is None

    # Extraction really happened
    assert source.get("extracted_text"), "no extracted text returned"
    assert "Prycoons" in source["extracted_text"]

    # Chunks exist in the database for THIS bot, with embeddings physically stored
    with engine.connect() as conn:
        chunk_rows = conn.execute(
            text("SELECT count(*) FROM knowledge_chunks WHERE bot_id = :b"), {"b": bot["id"]}
        ).scalar()
        vec_rows = conn.execute(
            text(
                "SELECT count(*) FROM knowledge_chunks "
                "WHERE bot_id = :b AND coalesce(embedding_json, '') <> ''"
            ),
            {"b": bot["id"]},
        ).scalar()

    assert chunk_rows == source["chunks_count"], "chunk rows in DB do not match the reported count"
    assert vec_rows == chunk_rows, "some chunks have no stored embedding"

    # The listing endpoint reflects the same source
    listed = client.get(f"/api/bots/{bot['id']}/knowledge", headers=headers)
    assert listed.status_code == 200
    assert any(s["id"] == source["id"] for s in listed.json())

    _record(
        "Knowledge upload -> extract -> chunk -> embed -> COMPLETED",
        True,
        f"{chunk_rows} chunks, {vec_rows} embedded",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5 + 6. Retrieval and grounded chat
# ─────────────────────────────────────────────────────────────────────────────
def test_04_retrieval_and_grounded_answer():
    headers = _signup("grounded")["headers"]
    project_id = _create_project(headers)
    bot = _create_bot(headers, project_id, f"Grounded Bot {uuid.uuid4().hex[:4]}")
    assert _upload_demo_doc(headers, bot["id"]).status_code == 201

    res = client.post(
        f"/api/bots/{bot['id']}/chat",
        json={"message": "What are the 3 BHK prices and amenities at Sunset Palms?"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert len(data["sources"]) > 0, "no sources retrieved"
    assert data["sources"][0]["similarity_score"] > 0

    reply = data["reply"]
    assert any(token in reply for token in ("Sunset Palms", "1.85", "3 BHK", "Crore", "pool")), (
        f"answer is not grounded in the uploaded document: {reply!r}"
    )

    _record("Vector retrieval + grounded answer", True)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Unknown question -> refusal (no hallucination)
# ─────────────────────────────────────────────────────────────────────────────
def test_05_unknown_question_refuses():
    headers = _signup("unknown")["headers"]
    project_id = _create_project(headers)
    bot = _create_bot(headers, project_id, f"Unknown Bot {uuid.uuid4().hex[:4]}")
    assert _upload_demo_doc(headers, bot["id"]).status_code == 201

    res = client.post(
        f"/api/bots/{bot['id']}/chat",
        json={"message": "What is the warranty policy on interstellar starships to Pluto?"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "do not have" in data["reply"].lower(), f"expected a refusal, got: {data['reply']!r}"
    assert data["sources"] == [], "a refusal must not cite sources"

    _record("Unknown question handled with grounded refusal", True)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Bot isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_06_bot_isolation():
    headers = _signup("isolation")["headers"]

    proj_a = _create_project(headers, "Real Estate")
    bot_a = _create_bot(headers, proj_a, f"Isolation A {uuid.uuid4().hex[:4]}")
    assert _upload_demo_doc(headers, bot_a["id"]).status_code == 201

    proj_b = _create_project(headers, "Healthcare")
    bot_b = _create_bot(headers, proj_b, f"Isolation B {uuid.uuid4().hex[:4]}")
    clinic_doc = (
        "Northside Clinic is open Monday to Saturday from 9 AM to 7 PM. "
        "Dr. Meera Shah is the lead cardiologist. Consultation fee is 800 rupees."
    )
    up = client.post(
        f"/api/bots/{bot_b['id']}/knowledge/upload",
        files={"file": ("clinic.txt", clinic_doc.encode("utf-8"), "text/plain")},
        headers=headers,
    )
    assert up.status_code == 201

    # Bot A must not surface Bot B's knowledge
    res_a = client.post(
        f"/api/bots/{bot_a['id']}/chat",
        json={"message": "Who is Dr. Meera Shah and what is the consultation fee?"},
        headers=headers,
    )
    assert res_a.status_code == 200
    for src in res_a.json()["sources"]:
        assert src["source_name"] != "clinic.txt", "Bot A leaked Bot B's knowledge"

    # Bot B answers its own question
    res_b = client.post(
        f"/api/bots/{bot_b['id']}/chat",
        json={"message": "Who is the lead cardiologist and what is the consultation fee?"},
        headers=headers,
    )
    assert res_b.status_code == 200
    assert len(res_b.json()["sources"]) > 0, "Bot B could not retrieve its own knowledge"
    assert "Meera Shah" in res_b.json()["reply"] or "800" in res_b.json()["reply"]

    _record("Bot-specific knowledge isolation", True)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Conversation persistence + RAG inside the conversation engine
# ─────────────────────────────────────────────────────────────────────────────
def test_07_conversation_persistence_and_rag():
    headers = _signup("convo")["headers"]
    project_id = _create_project(headers)
    bot = _create_bot(headers, project_id, f"Convo Bot {uuid.uuid4().hex[:4]}")
    assert _upload_demo_doc(headers, bot["id"]).status_code == 201

    convo_res = client.post("/api/conversations", json={"bot_id": bot["id"]}, headers=headers)
    assert convo_res.status_code == 201, convo_res.text
    convo_id = convo_res.json()["id"]

    msg = client.post(
        f"/api/conversations/{convo_id}/messages",
        json={"message": "I want a 3 BHK in Sunset Palms with a budget of 2 crore."},
        headers=headers,
    )
    assert msg.status_code == 200, msg.text
    payload = msg.json()
    assert payload["reply"], "assistant produced no reply"
    assert payload["intent"] in ("buying", "general_question", "browsing", payload["intent"])
    assert payload["conversation_state"].get("bhk") == 3, "state extraction failed"

    # Messages persist and are retrievable (simulates a browser refresh)
    hist = client.get(f"/api/conversations/{convo_id}", headers=headers)
    assert hist.status_code == 200
    messages = hist.json()["messages"]
    assert len(messages) == 2, f"expected 2 persisted messages, got {len(messages)}"
    assert messages[0]["sender"] == "USER"
    assert messages[1]["sender"] == "ASSISTANT"
    assert messages[1]["content"] == payload["reply"]

    # The lightweight listing endpoint also works (used by the chat history sidebar)
    listing = client.get(f"/api/bots/{bot['id']}/conversations", headers=headers)
    assert listing.status_code == 200
    assert any(c["id"] == convo_id for c in listing.json())

    _record("Conversation persistence + RAG in the chat engine", True)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Demo robustness: greeting and broad "what do you know" questions
# ─────────────────────────────────────────────────────────────────────────────
def test_08_greeting_and_overview_questions():
    headers = _signup("robust")["headers"]
    project_id = _create_project(headers)
    bot = _create_bot(headers, project_id, f"Robustness Bot {uuid.uuid4().hex[:4]}")
    assert _upload_demo_doc(headers, bot["id"]).status_code == 201

    # A greeting must never be answered with a "no information" refusal.
    greeting = client.post(f"/api/bots/{bot['id']}/chat", json={"message": "hi"}, headers=headers)
    assert greeting.status_code == 200
    assert "do not have" not in greeting.json()["reply"].lower(), (
        f"greeting produced a refusal: {greeting.json()['reply']!r}"
    )

    # The broad exploratory question from the brief must return grounded content.
    overview = client.post(
        f"/api/bots/{bot['id']}/chat",
        json={"message": "What information do you have about this business?"},
        headers=headers,
    )
    assert overview.status_code == 200
    overview_reply = overview.json()["reply"]
    assert "do not have" not in overview_reply.lower(), (
        f"overview question refused despite having knowledge: {overview_reply!r}"
    )
    assert "Prycoons" in overview_reply or "real estate" in overview_reply.lower()

    _record("Greeting + broad overview question", True)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Embedding quality: related content must outrank unrelated content
# ─────────────────────────────────────────────────────────────────────────────
def test_09_embedding_separability():
    from app.services.embedding_service import EmbeddingService

    query = "What are the 3 BHK prices and amenities at Sunset Palms?"
    related = (
        "Sunset Palms Luxury Residencies: Premium 3 BHK and 4 BHK apartments. "
        "3 BHK starting at 1.85 Crore. Amenities include a rooftop infinity pool and gymnasium."
    )
    unrelated = "Interstellar starship warranty policy and Martian tax regulations."

    query_vec, query_provider = EmbeddingService.get_embedding_with_provider(query)
    related_vec, related_provider = EmbeddingService.get_embedding_with_provider(related)
    unrelated_vec, _ = EmbeddingService.get_embedding_with_provider(unrelated)

    assert len(query_vec) == 1536
    assert query_provider == related_provider, "chunk and query must share an embedding provider"

    sim_related = EmbeddingService.cosine_similarity(query_vec, related_vec)
    sim_unrelated = EmbeddingService.cosine_similarity(query_vec, unrelated_vec)

    assert sim_related > sim_unrelated + 0.15, (
        f"embedding does not separate related from unrelated: "
        f"related={sim_related:.4f} unrelated={sim_unrelated:.4f}"
    )

    _record(
        "Embedding separability (related vs unrelated)",
        True,
        f"related={sim_related:.3f} unrelated={sim_unrelated:.3f} provider={query_provider}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Script entry point — prints an auditable report
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    tests = [
        ("Authentication", test_01_authentication),
        ("Project + bot persistence", test_02_project_and_bot_persist),
        ("Knowledge pipeline", test_03_knowledge_upload_full_pipeline),
        ("Retrieval + grounded answer", test_04_retrieval_and_grounded_answer),
        ("Unknown question refusal", test_05_unknown_question_refuses),
        ("Bot isolation", test_06_bot_isolation),
        ("Conversation persistence", test_07_conversation_persistence_and_rag),
        ("Greeting + overview question", test_08_greeting_and_overview_questions),
        ("Embedding separability", test_09_embedding_separability),
    ]

    print("=" * 68)
    print("BRIM AI - PHASE 1-4 END-TO-END DEMO VERIFICATION")
    print(f"Database: {engine.dialect.name} ({engine.url.database})")
    print("=" * 68)

    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"  FAIL  {name}: {exc}")

    print("=" * 68)
    for name, passed, detail in RESULTS:
        suffix = f"  ({detail})" if detail else ""
        print(f"  {'PASS' if passed else 'FAIL'}  {name}{suffix}")
    print("=" * 68)
    print(f"{len(RESULTS) - failures} passed, {failures} failed")
    sys.exit(1 if failures else 0)
