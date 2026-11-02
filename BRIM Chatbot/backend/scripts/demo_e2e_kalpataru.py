"""
Full demo dry-run: real website crawl + document upload + RAG questions + contextual greeting.

Run from backend/:  python scripts/demo_e2e_kalpataru.py
"""

import time
import uuid
from pathlib import Path

import httpx
from docx import Document

API = "http://127.0.0.1:8000/api"
SITE = "https://www.kalpataru.com/"

client = httpx.Client(timeout=300.0)

# ── Account, project, bot ─────────────────────────────────────────────────────
suffix = uuid.uuid4().hex[:6]
email = f"kalpataru_{suffix}@brimtest.com"
token = client.post(
    f"{API}/auth/signup",
    json={"name": "Kalpataru Demo", "email": email, "password": "Demo@12345"},
).json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

project = client.post(
    f"{API}/projects",
    json={"name": "Kalpataru Demo", "industry": "Real Estate", "description": "Demo project"},
    headers=h,
).json()
bot = client.post(
    f"{API}/bots",
    json={
        "project_id": project["id"],
        "name": "Kalpataru Property Advisor",
        "status": "Live",
        "welcome_message": "Hello! Ask me about Kalpataru projects.",
    },
    headers=h,
).json()
print(f"project={project['id']} bot={bot['id']} ({bot['name']})")

# ── Website crawl ─────────────────────────────────────────────────────────────
started = time.time()
site = client.post(
    f"{API}/bots/{bot['id']}/knowledge/website",
    json={"url": SITE, "name": "Kalpataru website", "max_pages": 3},
    headers=h,
)
print(f"website HTTP {site.status_code} in {time.time() - started:.1f}s")
site.raise_for_status()
site_data = site.json()
print(
    f"  status={site_data['processing_status']} chunks={site_data['chunks_count']} "
    f"error={site_data.get('error_message')}"
)

# ── Document upload ──────────────────────────────────────────────────────────
doc_path = Path("_kalpataru_brief.docx")
document = Document()
document.add_heading("Palm Grove Residency — Resident Brief", level=1)
document.add_paragraph(
    "Palm Grove Residency is a Kalpataru development in Thane with 2 and 3 BHK apartments."
)
document.add_paragraph(
    "The clubhouse is open from 6:00 AM to 11:00 PM every day, including public holidays."
)
document.add_paragraph("The annual maintenance fee is INR 42,000 per apartment.")
document.add_paragraph("Visitor parking is available in the basement level P2.")
document.save(doc_path)

with doc_path.open("rb") as handle:
    upload = client.post(
        f"{API}/bots/{bot['id']}/knowledge/upload",
        files={"file": (doc_path.name, handle, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=h,
    )
upload.raise_for_status()
up = upload.json()
print(f"document status={up['processing_status']} chunks={up['chunks_count']}")

# ── Wait for processing ─────────────────────────────────────────────────────
for _ in range(30):
    if up["processing_status"] in ("COMPLETED", "FAILED"):
        break
    time.sleep(2)
    up = client.get(f"{API}/bots/{bot['id']}/knowledge/{up['id']}", headers=h).json()
print(f"document final={up['processing_status']} chunks={up['chunks_count']}")

# ── Chat questions ──────────────────────────────────────────────────────────
QUESTIONS = [
    ("WEBSITE", "Which projects does Kalpataru have in Mumbai?"),
    ("DOCUMENT", "What are the clubhouse timings at Palm Grove Residency?"),
    ("UNKNOWN", "What is the warranty policy on interstellar starships to Pluto?"),
]

for label, question in QUESTIONS:
    answer = client.post(
        f"{API}/bots/{bot['id']}/chat", json={"message": question}, headers=h
    ).json()
    sources = [s.get("source_name") for s in answer.get("sources", [])]
    print(f"\n[{label}] {question}")
    print(f"  reply: {answer['reply'][:280]}")
    print(f"  sources={sources} confidence={answer.get('confidence')}")

# ── Contextual greeting ─────────────────────────────────────────────────────
for city, hour in (("Mumbai", 10), (None, 22)):
    greeting = client.post(
        f"{API}/context/greeting",
        json={"language": "en", "city": city, "local_hour": hour},
        headers=h,
    ).json()
    print(f"\n[GREETING city={city} hour={hour}] decision={greeting['decision']}")
    print(f"  {greeting['text'][:220]}")
    print(f"  context={greeting['context']}")

print(f"\nUI: http://localhost:8080  ·  login {email} / Demo@12345")
