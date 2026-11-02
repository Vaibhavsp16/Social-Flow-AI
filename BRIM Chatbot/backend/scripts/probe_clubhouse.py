import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.database.session import SessionLocal
from app.services.retrieval_service import RetrievalService

API = "http://127.0.0.1:8000/api"
BOT = 1143

login = httpx.post(
    f"{API}/auth/login",
    json={"email": "kalpataru_5df6f5@brimtest.com", "password": "Demo@12345"},
    timeout=30,
).json()
h = {"Authorization": f"Bearer {login['access_token']}"}

for question in (
    "What are the clubhouse timings at Palm Grove Residency?",
    "clubhouse timings",
    "What is the annual maintenance fee?",
):
    answer = httpx.post(f"{API}/bots/{BOT}/chat", json={"message": question}, headers=h, timeout=120).json()
    print(f"\nQ: {question}")
    print(f"  conf={answer.get('confidence')} sources={len(answer.get('sources') or [])}")
    print(f"  {answer['reply'][:150]}")

db = SessionLocal()
try:
    for question in ("What are the clubhouse timings at Palm Grove Residency?", "clubhouse timings"):
        rows = RetrievalService.search_relevant_chunks(db, BOT, question, top_k=4, threshold=0.0)
        print(f"\nRAW scores for: {question}")
        for chunk, score in rows[:4]:
            print(f"  {score:.3f}  {chunk.source_name[:40]}  {chunk.content[:60]!r}")
finally:
    db.close()
