"""Post-run state check: source uniqueness and a single question repeated three times."""
import os
from collections import Counter

import httpx

from app.database.session import SessionLocal
from app.models.knowledge_source import KnowledgeSource

db = SessionLocal()
rows = db.query(KnowledgeSource).filter(KnowledgeSource.bot_id == 1380).all()
counts = Counter(r.original_filename or r.name for r in rows)
print("sources:", len(rows), "| unique:", len(counts))
for name, number in counts.items():
    print(f"  {'DUP ' if number > 1 else ''}{name} x{number}")

A = os.getenv("BRIM_API", "http://127.0.0.1:8000/api")
client = httpx.Client(timeout=180)
token = client.post(
    f"{A}/auth/login", json={"email": "demo@brim.ai", "password": "Demo@12345"}
).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
convo = client.post(
    f"{A}/conversations", json={"bot_id": 1380, "language": "en", "local_hour": 12}, headers=H
).json()
print("\nconversation", convo["id"])
for _ in range(3):
    body = client.post(
        f"{A}/conversations/{convo['id']}/messages",
        json={"message": "What is the carpet area of the units?"},
        headers=H,
    ).json()
    print(f"  reply: {body['reply'][:160]!r} | conf {body['confidence']}")
