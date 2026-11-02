"""Ad-hoc crawl probe: verify multi-page scoping against real BRIM URLs."""

import json
import uuid

import httpx

API = "http://127.0.0.1:8000/api"
client = httpx.Client(timeout=300.0)
email = f"crawl_{uuid.uuid4().hex[:8]}@brimtest.com"
token = client.post(
    f"{API}/auth/signup", json={"name": "Crawl", "email": email, "password": "Crawl@12345"}
).json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
project = client.post(f"{API}/projects", json={"name": "Crawl", "industry": "Other"}, headers=headers).json()
bot = client.post(f"{API}/bots", json={"project_id": project["id"], "name": "Crawl Bot"}, headers=headers).json()

for url, max_pages in [
    ("https://brim.co.in/industry/", 8),
    ("https://brim.co.in/", 3),
]:
    response = client.post(
        f"{API}/bots/{bot['id']}/knowledge/website",
        json={"url": url, "max_pages": max_pages},
        headers=headers,
    )
    body = response.json()
    meta = json.loads(body.get("metadata_json") or "{}")
    print(f"\n{url} max_pages={max_pages} -> {response.status_code} {body.get('processing_status')}")
    print(f"  chunks={body.get('chunks_count')} pages={meta.get('pages_crawled')} chars={meta.get('character_count')}")
    for page in meta.get("pages", []):
        print(f"   - {page['url']} ({page['character_count']})")
    if body.get("error_message"):
        print(f"  error: {body['error_message']}")
