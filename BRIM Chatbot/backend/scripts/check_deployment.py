"""
Full smoke test against a deployed BRIM AI instance.

Exercises the paths a demo depends on: auth, project and bot creation, document ingestion
(including an image-only PDF that needs OCR), a grounded answer, a grounded refusal, and the
analytics endpoint. Prints PASS/FAIL per step; never hides a failure behind a retry.
"""
import os
import sys
import time
import uuid

import httpx

API = os.getenv("BRIM_API", "https://brim-api-dxgh.onrender.com/api")
ORIGIN = os.getenv("BRIM_ORIGIN", "https://social-flow-ai-frontend.vercel.app")
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_fixtures")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


client = httpx.Client(timeout=300, headers={"Origin": ORIGIN})

# 1. health
try:
    health = client.get(f"{API.replace('/api', '')}/health")
    check("backend /health", health.status_code == 200, health.text[:80])
except Exception as exc:  # noqa: BLE001
    check("backend /health", False, str(exc))
    print("\nBackend unreachable; stopping.")
    sys.exit(1)

# 2. signup on the deployed database
email = f"deploy.check.{uuid.uuid4().hex[:8]}@brimtest.com"
password = "Deploy@2026"
response = client.post(f"{API}/auth/signup", json={"name": "Deploy Check", "email": email, "password": password})
check("signup", response.status_code == 201, f"HTTP {response.status_code} {response.text[:120]}")
if response.status_code != 201:
    print("\nCannot continue without an account.")
    sys.exit(1)
token = response.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
print(f"     account: {email} / {password}")

# 3. authenticated identity
me = client.get(f"{API}/auth/me", headers=H)
check("GET /auth/me", me.status_code == 200 and me.json().get("email") == email,
      f"role={me.json().get('role') if me.status_code == 200 else 'n/a'}")

# 4. login with the new credentials
login = client.post(f"{API}/auth/login", json={"email": email, "password": password})
check("login", login.status_code == 200, f"HTTP {login.status_code}")

# 5. project + bot
project = client.post(f"{API}/projects", headers=H, json={"name": "Deploy Project", "industry": "Real Estate"})
check("create project", project.status_code in (200, 201), f"HTTP {project.status_code} {project.text[:100]}")
project_id = project.json()["id"]

bot = client.post(f"{API}/bots", headers=H, json={"project_id": project_id, "name": "Deploy Bot", "status": "Live"})
check("create bot", bot.status_code in (200, 201), f"HTTP {bot.status_code} {bot.text[:100]}")
bot_id = bot.json()["id"]

# 6. ingestion — an image-only PDF (needs render + OCR) and a DOCX with tables
for filename, expect_min_chunks in (("brochure_images.pdf", 2), ("positioning.docx", 1)):
    started = time.time()
    with open(os.path.join(FIXTURES, filename), "rb") as handle:
        upload = client.post(
            f"{API}/bots/{bot_id}/knowledge/upload",
            headers=H,
            files={"file": (filename, handle, "application/octet-stream")},
        )
    elapsed = time.time() - started
    if upload.status_code >= 400:
        check(f"upload {filename}", False, f"HTTP {upload.status_code} {upload.text[:140]}")
        continue
    body = upload.json()
    check(
        f"upload {filename}",
        body.get("processing_status") == "COMPLETED" and (body.get("chunks_count") or 0) >= expect_min_chunks,
        f"status={body.get('processing_status')} chunks={body.get('chunks_count')} in {elapsed:.0f}s",
    )

# 7. conversation greeting
convo = client.post(f"{API}/conversations", headers=H, json={"bot_id": bot_id, "language": "en", "local_hour": 11})
check("create conversation", convo.status_code in (200, 201), f"HTTP {convo.status_code}")
conversation = convo.json()
greeting = conversation["messages"][0]["content"] if conversation.get("messages") else ""
check("greeting is one welcome + one question", "Welcome to the chat" in greeting and greeting.count("?") <= 1,
      greeting.replace("\n", " | ")[:120])

# 8. grounded answer from the OCR'd brochure
answer = client.post(
    f"{API}/conversations/{conversation['id']}/messages",
    headers=H,
    json={"message": "What is the carpet area given in the area statement?"},
).json()
check(
    "grounded answer (OCR content)",
    "4105.85" in answer["reply"] and len(answer.get("sources") or []) > 0,
    f"conf={answer.get('confidence')} sources={len(answer.get('sources') or [])} :: {answer['reply'][:90]}",
)

# 9. table content from the DOCX
answer2 = client.post(
    f"{API}/conversations/{conversation['id']}/messages",
    headers=H,
    json={"message": "Which channel gets the largest budget share?"},
).json()
check(
    "grounded answer (DOCX table)",
    "instagram" in answer2["reply"].lower() and len(answer2.get("sources") or []) > 0,
    f"conf={answer2.get('confidence')} :: {answer2['reply'][:90]}",
)

# 10. refusal with no citations
refusal = client.post(
    f"{API}/conversations/{conversation['id']}/messages",
    headers=H,
    json={"message": "What is the warranty on interstellar starships to Pluto?"},
).json()
check(
    "refusal with zero citations",
    "do not have enough information" in refusal["reply"].lower() and not (refusal.get("sources") or []),
    f"sources={len(refusal.get('sources') or [])}",
)

# 11. analytics derives from real rows
analytics = client.get(f"{API}/analytics/bots/{bot_id}", headers=H)
check("analytics endpoint", analytics.status_code == 200,
      f"HTTP {analytics.status_code} has_data={analytics.json().get('has_data') if analytics.status_code == 200 else 'n/a'}")

# 12. CORS on a real authenticated response
echo = client.options(f"{API}/auth/login", headers={
    "Origin": ORIGIN,
    "Access-Control-Request-Method": "POST",
})
check("CORS preflight", echo.status_code == 200 and echo.headers.get("access-control-allow-origin") == ORIGIN,
      echo.headers.get("access-control-allow-origin", "no header"))

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
print(f"bot_id={bot_id} conversation_id={conversation['id']}")
