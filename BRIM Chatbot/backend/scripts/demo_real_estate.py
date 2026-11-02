"""
Scripted end-to-end demo of the Prycoons real-estate workflow.

Run from backend/:  python scripts/demo_real_estate.py

Drives the buying, renting, browsing and handoff scenarios through the app (in-process, so no
server needs to be running) and prints every turn so the transcript can be checked at a glance.
Requires the database only.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api"
client = TestClient(app)


def banner(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def turn(headers, convo_id, text):
    response = client.post(
        f"{API}/conversations/{convo_id}/messages", json={"message": text}, headers=headers
    )
    response.raise_for_status()
    data = response.json()
    print(f"\nVISITOR: {text}")
    print(f"BOT     : {data['reply']}")
    if data.get("properties"):
        for prop in data["properties"]:
            print(
                f"          • {prop['title']} | {prop['bhk'] or '-'} BHK | {prop['location']} | "
                f"{prop['price_display']} | mock={prop['is_mock']}"
            )
    meta = [f"intent={data['intent']}", f"stage={data.get('stage')}"]
    if data.get("sources"):
        meta.append(f"citations={len(data['sources'])}")
    if data.get("lead"):
        meta.append(f"lead={data['lead']['name']}")
    print("          [" + " | ".join(meta) + "]")
    return data


def main() -> int:
    suffix = uuid.uuid4().hex[:6]
    email = f"demo_re_{suffix}@brimtest.com"

    token = client.post(
        f"{API}/auth/signup",
        json={"name": "Demo", "email": email, "password": "Demo@12345"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    project = client.post(
        f"{API}/projects", json={"name": f"Prycoons {suffix}", "industry": "Real Estate"}, headers=headers
    ).json()
    bot = client.post(
        f"{API}/bots",
        json={
            "project_id": project["id"],
            "name": "Prycoons Property Advisor",
            "welcome_message": "Hi! Are you looking to buy, rent, or explore?",
            "status": "Live",
        },
        headers=headers,
    ).json()

    def new_conversation():
        return client.post(f"{API}/conversations", json={"bot_id": bot["id"]}, headers=headers).json()["id"]

    banner("SCENARIO 1 — BUYING: requirements → shortlist → lead")
    convo = new_conversation()
    turn(headers, convo, "Hi")
    turn(headers, convo, "I'm looking to buy a 3 BHK apartment in Ambli, budget around 2 crore")
    turn(headers, convo, "The first one looks good, can someone call me?")
    turn(headers, convo, "Ravi Patel")
    turn(headers, convo, "98765 43210")
    turn(headers, convo, "ravi.patel@example.com")
    final = turn(headers, convo, "WhatsApp")

    banner("CAPTURED LEAD")
    leads = client.get(f"{API}/bots/{bot['id']}/leads", headers=headers).json()
    for lead in leads:
        print(
            f"#{lead['id']} {lead['name']} | {lead['phone']} | {lead['email']} | "
            f"{lead['preferred_contact']} | {lead['requirements']} | {lead['status']}"
        )
    assert final["lead"], "lead was not captured"

    banner("SCENARIO 2 — RENTING")
    convo = new_conversation()
    turn(headers, convo, "I want a 2 BHK on rent in Bopal under 40k")
    turn(headers, convo, "Tell me about the first one")

    banner("SCENARIO 3 — BROWSING (no lead push)")
    convo = new_conversation()
    turn(headers, convo, "Just looking at what's available")
    turn(headers, convo, "What's the price of the Thaltej one?")

    banner("SCENARIO 4 — HUMAN HANDOFF")
    convo = new_conversation()
    handoff = turn(headers, convo, "I'd rather speak to a human advisor")
    print(f"\nconversation status: {handoff['status']}")

    banner("SCENARIO 5 — NO INVENTED LISTINGS")
    convo = new_conversation()
    turn(headers, convo, "Do you have a 5 BHK penthouse in Gandhinagar?")

    print("\nAll scenarios completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
