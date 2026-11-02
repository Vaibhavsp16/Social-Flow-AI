"""
Analytics, reporting and admin: numbers must match the database, tenants must stay isolated and
CSV must equal the JSON rows.
"""

import csv
import io
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core.security import get_password_hash
from app.database.session import SessionLocal
from app.main import app
from app.models.conversation import Conversation, Message
from app.models.lead import Lead
from app.models.user import User

client = TestClient(app)


def _signup(prefix: str):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/api/auth/signup",
        json={"name": prefix.title(), "email": email, "password": "Test@12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


def _bot(headers, industry="Real Estate", name="Analytics Bot"):
    project = client.post(
        "/api/projects",
        json={"name": f"AN {uuid.uuid4().hex[:6]}", "industry": industry},
        headers=headers,
    ).json()
    return client.post(
        "/api/bots",
        json={"project_id": project["id"], "name": name, "status": "Live"},
        headers=headers,
    ).json()


def _new_conversation(headers, bot_id):
    return client.post("/api/conversations", json={"bot_id": bot_id}, headers=headers).json()


def _send(headers, convo_id, text):
    response = client.post(
        f"/api/conversations/{convo_id}/messages", json={"message": text}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def admin_headers():
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        db.add(User(name="Admin", email=email, password_hash=get_password_hash("Admin@12345"), role="ADMIN"))
        db.commit()
    finally:
        db.close()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "Admin@12345"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def dataset():
    """Owner A with three conversations (lead, browsing, handoff) and owner B with a bot."""
    a_headers, a_email = _signup("owner_a")
    b_headers, b_email = _signup("owner_b")

    a_bot = _bot(a_headers, name="Prycoons Analytics")

    # 1. Buying conversation that ends in a lead.
    c1 = _new_conversation(a_headers, a_bot["id"])
    _send(a_headers, c1["id"], "I'm looking to buy a 3 BHK apartment in Ambli, budget 2 crore")
    _send(a_headers, c1["id"], "yes please arrange a call")
    _send(a_headers, c1["id"], "Analytics Buyer")
    _send(a_headers, c1["id"], "9876500011")
    _send(a_headers, c1["id"], "buyer@example.com")
    _send(a_headers, c1["id"], "WhatsApp")

    # 2. Browsing conversation, no lead.
    c2 = _new_conversation(a_headers, a_bot["id"])
    _send(a_headers, c2["id"], "just looking at what's available")

    # 3. Handoff request.
    c3 = _new_conversation(a_headers, a_bot["id"])
    _send(a_headers, c3["id"], "I want to speak to a human advisor")
    client.post(f"/api/conversations/{c3['id']}/handoff", headers=a_headers)

    b_bot = _bot(b_headers, name="Other Tenant Bot")

    return {
        "a_headers": a_headers,
        "a_email": a_email,
        "b_headers": b_headers,
        "b_email": b_email,
        "a_bot": a_bot,
        "b_bot": b_bot,
        "conversations": [c1["id"], c2["id"], c3["id"]],
    }


# ── Analytics ────────────────────────────────────────────────────────────────

def test_bot_analytics_match_database(dataset):
    payload = client.get(
        f"/api/analytics/bots/{dataset['a_bot']['id']}", headers=dataset["a_headers"]
    ).json()

    db = SessionLocal()
    try:
        bot_id = dataset["a_bot"]["id"]
        conversations = db.query(Conversation).filter(Conversation.bot_id == bot_id).all()
        convo_ids = [c.id for c in conversations]
        messages = db.query(Message).filter(Message.conversation_id.in_(convo_ids)).count()
        leads = db.query(Lead).filter(Lead.bot_id == bot_id).count()
        handoffs = sum(
            1 for c in conversations if c.status in ("HANDOFF_REQUESTED", "HANDED_OFF")
        )
    finally:
        db.close()

    assert payload["totals"]["conversations"] == len(conversations) == 3
    assert payload["totals"]["messages"] == messages
    assert payload["totals"]["leads"] == leads == 1
    assert payload["totals"]["handoffs"] == handoffs == 1
    assert payload["totals"]["unique_users"] == 3
    assert payload["totals"]["avg_messages_per_conversation"] == round(messages / 3, 1)
    assert payload["has_data"] is True


def test_intent_distribution_and_resolution(dataset):
    payload = client.get(
        f"/api/analytics/bots/{dataset['a_bot']['id']}", headers=dataset["a_headers"]
    ).json()

    assert payload["intents"]["buying"] == 1
    assert payload["intents"]["browsing"] == 1
    # One conversation produced a lead, one requested a handoff, one is still open.
    assert payload["totals"]["resolved"] == 1
    assert payload["totals"]["unresolved"] == 2
    assert payload["totals"]["resolution_rate"] == pytest.approx(33.3, abs=0.1)
    assert payload["totals"]["lead_conversion_rate"] == pytest.approx(33.3, abs=0.1)
    assert payload["volume"], "conversation volume should have at least one day"


def test_empty_bot_reports_no_data(dataset):
    payload = client.get(
        f"/api/analytics/bots/{dataset['b_bot']['id']}", headers=dataset["b_headers"]
    ).json()
    assert payload["has_data"] is False
    assert payload["totals"]["conversations"] == 0
    assert payload["totals"]["resolution_rate"] == 0.0
    assert payload["volume"] == []


def test_date_range_filter_excludes_future(dataset):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = client.get(
        f"/api/analytics/bots/{dataset['a_bot']['id']}",
        params={"start": tomorrow, "end": tomorrow},
        headers=dataset["a_headers"],
    ).json()
    assert payload["totals"]["conversations"] == 0
    assert payload["has_data"] is False


# ── Tenant isolation ─────────────────────────────────────────────────────────

def test_business_cannot_read_another_tenants_bot(dataset):
    response = client.get(
        f"/api/analytics/bots/{dataset['a_bot']['id']}", headers=dataset["b_headers"]
    )
    assert response.status_code == 404


def test_business_reports_are_scoped(dataset):
    payload = client.get("/api/reports/conversations", headers=dataset["b_headers"]).json()
    assert payload["rows"] == []
    assert payload["summary"]["conversations"] == 0

    owner = client.get("/api/reports/conversations", headers=dataset["a_headers"]).json()
    assert len(owner["rows"]) == 3


def test_business_cannot_reach_admin(dataset):
    for path in ("/api/admin/overview", "/api/admin/users", "/api/admin/leads", "/api/admin/activity"):
        response = client.get(path, headers=dataset["a_headers"])
        assert response.status_code == 403, path


# ── Admin ────────────────────────────────────────────────────────────────────

def test_admin_sees_platform_data(admin_headers, dataset):
    overview = client.get("/api/admin/overview", headers=admin_headers).json()
    assert overview["entities"]["users"] >= 3
    assert overview["entities"]["bots"] >= 2
    assert overview["totals"]["conversations"] >= 3

    users = client.get("/api/admin/users", headers=admin_headers).json()
    assert users["total"] >= 3
    assert all("password" not in item for item in users["items"])

    leads = client.get("/api/admin/leads", headers=admin_headers).json()
    assert leads["total"] >= 1
    # End-customer contact details are masked.
    assert all(item["phone"].startswith("*") for item in leads["items"])

    bots = client.get("/api/admin/bots", headers=admin_headers).json()
    assert any(item["id"] == dataset["a_bot"]["id"] for item in bots["items"])


def test_activity_events_recorded(admin_headers):
    events = client.get("/api/admin/activity", params={"limit": 200}, headers=admin_headers).json()
    kinds = {item["event_type"] for item in events["items"]}
    for expected in (
        "user_signup", "project_created", "bot_created", "conversation_started",
        "lead_captured", "bot_published",
    ):
        assert expected in kinds, f"missing activity event: {expected}"


# ── Reports + CSV ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["conversations", "leads", "bot_usage", "intents", "handoffs", "unanswered"])
def test_csv_matches_json_rows(kind, dataset):
    json_report = client.get(f"/api/reports/{kind}", headers=dataset["a_headers"]).json()
    csv_response = client.get(
        f"/api/reports/{kind}", params={"format": "csv"}, headers=dataset["a_headers"]
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")

    text = csv_response.content.decode("utf-8-sig")
    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed[0] == json_report["columns"]
    assert len(parsed) - 1 == len(json_report["rows"])


def test_report_rows_reflect_lead_data(dataset):
    report = client.get("/api/reports/leads", headers=dataset["a_headers"]).json()
    assert report["summary"]["leads"] == 1
    row = report["rows"][0]
    assert row[report["columns"].index("name")] == "Analytics Buyer"
    phone = row[report["columns"].index("phone_masked")]
    assert phone.endswith("0011") and phone.startswith("*")
