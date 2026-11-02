"""
Scenario tests for the Prycoons real-estate workflow:
buying, renting, browsing, lead capture and human handoff.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.services.property_service import PropertyService

client = TestClient(app)


@pytest.fixture
def account():
    email = f"reflow_{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/api/auth/signup",
        json={"name": "Real Estate Tester", "email": email, "password": "Test@12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_bot(headers, industry="Real Estate", name="Prycoons Advisor"):
    project = client.post(
        "/api/projects",
        json={"name": f"RE {uuid.uuid4().hex[:6]}", "industry": industry},
        headers=headers,
    ).json()
    bot = client.post(
        "/api/bots",
        json={
            "project_id": project["id"],
            "name": name,
            "welcome_message": "Hi! Are you looking to buy, rent, or explore?",
            "status": "Live",
        },
        headers=headers,
    ).json()
    convo = client.post(
        "/api/conversations", json={"bot_id": bot["id"]}, headers=headers
    ).json()
    return bot, convo


def say(headers, convo_id, text):
    response = client.post(
        f"/api/conversations/{convo_id}/messages",
        json={"message": text},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_property_inventory_endpoint(account):
    bot, _ = make_bot(account)
    response = client.get(f"/api/bots/{bot['id']}/properties", headers=account)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 10
    assert all(row["is_mock"] for row in rows)
    assert {row["listing_type"] for row in rows} == {"SALE", "RENT"}

    seeded = client.post(f"/api/bots/{bot['id']}/properties/seed", headers=account).json()
    assert seeded["inserted"] == 0  # idempotent
    assert seeded["total"] == len(rows)


def test_buying_flow_shortlist_then_lead(account):
    bot, convo = make_bot(account)

    first = say(account, convo["id"], "Hi")
    # A greeting is answered warmly and briefly; it no longer opens with a menu of questions.
    assert first["reply"].strip()
    assert first["reply"].count("?") <= 1

    second = say(account, convo["id"], "I want to buy a home")
    assert second["intent"] == "buying"
    # A plain "Hi" no longer advances the workflow; it is answered conversationally.
    assert second["stage"] in ("greeting", "discover")

    third = say(account, convo["id"], "In Ambli")
    assert third["conversation_state"]["location"] == "Ambli"

    fourth = say(account, convo["id"], "3 BHK apartment, budget around 2 crore")
    assert fourth["stage"] == "shortlist"
    assert fourth["properties"], "expected a shortlist for Ambli 3 BHK"
    top = fourth["properties"][0]
    assert top["location"].lower() == "ambli"
    assert top["bhk"] == 3
    assert top["price_display"]
    assert top["is_mock"] is True

    ask = say(account, convo["id"], "Yes please arrange a call")
    assert ask["conversation_state"]["lead_pending"] == "lead_name"

    name = say(account, convo["id"], "Ravi Patel")
    assert name["conversation_state"]["lead_pending"] == "lead_phone"

    phone = say(account, convo["id"], "98765 43210")
    assert phone["conversation_state"]["lead_pending"] == "lead_email"

    email = say(account, convo["id"], "ravi.patel@example.com")
    assert email["conversation_state"]["lead_pending"] == "lead_contact"

    done = say(account, convo["id"], "WhatsApp")
    assert done["conversation_state"]["stage"] == "confirm"
    assert done["lead"]["name"] == "Ravi Patel"
    assert done["lead"]["preferred_contact"] == "WhatsApp"

    leads = client.get(f"/api/bots/{bot['id']}/leads", headers=account).json()
    assert len(leads) == 1
    assert leads[0]["phone"].endswith("43210")
    assert "3 BHK" in leads[0]["requirements"]


def test_renting_flow_returns_only_rentals(account):
    bot, convo = make_bot(account)
    reply = say(account, convo["id"], "I need a 2 BHK on rent in Bopal under 40k")
    assert reply["intent"] == "renting"
    assert reply["stage"] == "shortlist"
    assert reply["properties"], "expected rental options"
    assert all(p["listing_type"] == "RENT" for p in reply["properties"])
    assert all(p["bhk"] == 2 for p in reply["properties"])
    assert all(p["price"] <= 40000 * 1.2 for p in reply["properties"])


def test_browsing_does_not_push_lead(account):
    bot, convo = make_bot(account)
    reply = say(account, convo["id"], "Just looking at what's available")
    assert reply["intent"] == "browsing"
    assert reply["properties"]
    lowered = reply["reply"].lower()
    assert "phone" not in lowered and "should the advisor" not in lowered
    assert "advisor" not in lowered or "if you" in lowered


def test_handoff_request(account):
    bot, convo = make_bot(account)
    reply = say(account, convo["id"], "I want to speak to a human advisor")
    assert reply["is_handoff"] is True
    assert reply["status"] == "HANDOFF_REQUESTED"

    detail = client.get(f"/api/conversations/{convo['id']}", headers=account).json()
    assert detail["status"] == "HANDOFF_REQUESTED"


def test_no_invented_listings(account):
    bot, convo = make_bot(account)
    reply = say(account, convo["id"], "Do you have a 5 BHK penthouse in Gandhinagar?")
    assert reply["properties"] == []
    lowered = reply["reply"].lower()
    assert "could not find" in lowered or "widen" in lowered
    assert "5 bhk penthouse" not in lowered.replace("do you have a 5 bhk penthouse", "")


def test_sold_property_is_not_offered(account):
    bot, _ = make_bot(account)
    rows = client.get(f"/api/bots/{bot['id']}/properties", headers=account).json()
    assert any(row["status"] == "SOLD" for row in rows)  # exists in dev data

    db = SessionLocal()
    try:
        matches = PropertyService.search(
            db,
            bot["id"],
            listing_type="SALE",
            location="Ambli",
            bhk=2,
            limit=10,
        )
    finally:
        db.close()

    assert all(m["status"] == "AVAILABLE" for m in matches)
    assert all(m["property_id"] != "PRY-ORION-2BHK" for m in matches)


def test_other_industries_are_not_affected(account):
    bot, convo = make_bot(account, industry="Healthcare", name="Clinic Assistant")
    reply = say(account, convo["id"], "I want to buy a 3 BHK in Ambli")
    assert reply["properties"] == []
    assert reply["stage"] is None
