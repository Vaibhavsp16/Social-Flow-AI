"""
Create (or refresh) the demo account used to show BRIM AI.

Run from backend/:  python scripts/seed_demo_account.py

Idempotent: if the account already exists it logs in instead of signing up, and the demo bot's
industry pack is re-seeded (seeding the same pack refreshes it rather than duplicating).
"""

import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

API = "http://127.0.0.1:8000/api"
EMAIL = "demo@brim.ai"
PASSWORD = "Demo@12345"
NAME = "BRIM Demo"

INDUSTRY = "Real Estate"
PACK_KEY = "real-estate"
PROJECT_NAME = "BRIM Branding Studio"
BOT_NAME = "BRIM Property Advisor"


def main() -> int:
    with httpx.Client(timeout=180.0) as client:
        signup = client.post(f"{API}/auth/signup", json={"name": NAME, "email": EMAIL, "password": PASSWORD})
        if signup.status_code == 200:
            token = signup.json()["access_token"]
            print(f"Created demo account {EMAIL}")
        else:
            login = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
            login.raise_for_status()
            token = login.json()["access_token"]
            print(f"Logged in as existing demo account {EMAIL}")

        headers = {"Authorization": f"Bearer {token}"}

        projects = client.get(f"{API}/projects", headers=headers).json()
        project = next((p for p in projects if p["name"] == PROJECT_NAME), None)
        if project is None:
            project = client.post(
                f"{API}/projects",
                json={"name": PROJECT_NAME, "industry": INDUSTRY,
                      "description": "Demonstration workspace for BRIM industry chatbots."},
                headers=headers,
            ).json()
            print(f"Created project {PROJECT_NAME!r}")

        bots = client.get(f"{API}/bots", params={"project_id": project["id"]}, headers=headers).json()
        bot = next((b for b in bots if b["name"] == BOT_NAME), None)
        if bot is None:
            bot = client.post(
                f"{API}/bots",
                json={"project_id": project["id"], "name": BOT_NAME,
                      "description": "Answers questions about BRIM's real estate branding services.",
                      "welcome_message": "Hi! Ask me anything about BRIM's real estate branding services.",
                      "status": "Live"},
                headers=headers,
            ).json()
            print(f"Created bot {BOT_NAME!r}")

        seeded = client.post(
            f"{API}/bots/{bot['id']}/knowledge/seed-industry",
            json={"industry_key": PACK_KEY},
            headers=headers,
        )
        seeded.raise_for_status()
        source = seeded.json()
        print(f"Indexed {source['name']}: {source['chunks_count']} chunks ({source['processing_status']})")

        answer = client.post(
            f"{API}/bots/{bot['id']}/chat",
            json={"message": "What services does BRIM offer for real estate brands?"},
            headers=headers,
        )
        answer.raise_for_status()
        payload = answer.json()
        print(f"Smoke answer: {payload['reply'][:160]}...")
        print(f"Citations: {len(payload['sources'])} | confidence {payload['confidence']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
