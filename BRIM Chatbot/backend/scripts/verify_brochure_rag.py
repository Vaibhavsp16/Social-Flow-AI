"""Ingest a graphics-only brochure and ask questions of it end to end."""

import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api"
PDF = Path(r"C:\Users\Vaibhav.S.P\Downloads\Signature Brochure_1.pdf")

client = httpx.Client(timeout=300.0)
login = client.post(
    f"{API}/auth/login",
    json={"email": "demo@brim.ai", "password": "Demo@12345"},
)
token = login.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

project = client.post(
    f"{API}/projects",
    json={"name": "Signature Brochure", "industry": "Real Estate"},
    headers=h,
).json()
bot = client.post(
    f"{API}/bots",
    json={"project_id": project["id"], "name": "Signature Brochure Assistant", "status": "Live"},
    headers=h,
).json()
print(f"bot={bot['id']}")

with PDF.open("rb") as handle:
    upload = client.post(
        f"{API}/bots/{bot['id']}/knowledge/upload",
        files={"file": (PDF.name, handle, "application/pdf")},
        headers=h,
    )
upload.raise_for_status()
source = upload.json()
print(f"upload: {source['processing_status']} chunks={source['chunks_count']}")

for _ in range(40):
    if source["processing_status"] in ("COMPLETED", "FAILED"):
        break
    time.sleep(3)
    source = client.get(f"{API}/bots/{bot['id']}/knowledge/{source['id']}", headers=h).json()

print(f"final: {source['processing_status']} chunks={source['chunks_count']} err={source.get('error_message')}")

for question in (
    "Where is the Signature project located?",
    "Who is the developer and when was the company started?",
    "What amenities are listed for the basement?",
):
    answer = client.post(
        f"{API}/bots/{bot['id']}/chat", json={"message": question}, headers=h
    ).json()
    pages = [s.get("page_number") for s in answer.get("sources", [])]
    print(f"\nQ: {question}")
    print(f"   {answer['reply'][:300]}")
    print(f"   confidence={answer.get('confidence')} pages={pages}")
