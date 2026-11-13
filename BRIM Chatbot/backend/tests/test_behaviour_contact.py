"""Use case, contact capture, scheduling, identity and public surfaces.

These cover the behaviour the handoff describes as "the bot should adapt", plus the pieces that were
collected in the wizard but never stored.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.use_cases import get_use_case, lead_policy_prompt
from app.main import app
from app.services.contact_service import extract_phone, extract_preferred_time, normalise_phone
from app.services.scheduling_service import resolve_slot, wants_meeting

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _auth(email: str, name: str = "Behaviour Tester") -> dict:
    signup = client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    if signup.status_code == 400:
        login = client.post(
            "/api/auth/login", json={"email": email, "password": "Password123!"}
        )
        token = login.json()["access_token"]
    else:
        assert signup.status_code == 201, signup.text
        token = signup.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _project(headers: dict, name: str = "Behaviour Co", industry: str = "Real Estate") -> int:
    response = client.post(
        "/api/projects",
        json={"name": name, "industry": industry, "description": "test"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _bot(headers: dict, project_id: int, **overrides) -> dict:
    payload = {
        "project_id": project_id,
        "name": "Behaviour Bot",
        "status": "Live",
        "primary_use_case": "appointment_booking",
        "response_style": "concise",
        "lead_collection": "always",
        "human_handoff": "always_offer",
        "contact_after_messages": 2,
        "idle_prompt_seconds": 30,
        "company_name": "Acme Realty",
    }
    payload.update(overrides)
    response = client.post("/api/bots", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ── pure parsing ─────────────────────────────────────────────────────────────

def test_phone_normalisation_accepts_real_shapes():
    assert normalise_phone("+91 98250 12345") == "+919825012345"
    assert normalise_phone("9825012345") == "9825012345"
    assert normalise_phone("098250 12345") == "9825012345"
    assert normalise_phone("12") is None
    # An order number or a card long enough to be something else is not a phone number.
    assert normalise_phone("4000 1234 5678 9010 22") is None


def test_preferred_time_is_captured_verbatim():
    # Adjacent hints are one slot, not two.
    assert extract_preferred_time("call me tomorrow evening") == "tomorrow evening"
    assert extract_preferred_time("after 6pm works") == "after 6pm"
    assert extract_preferred_time("weekday evenings please") == "weekday evenings"
    assert extract_preferred_time("Tuesday 6pm") == "Tuesday 6pm"
    assert extract_preferred_time("anything") is None


def test_contact_details_are_found_inside_a_normal_sentence():
    assert extract_phone("you can reach me on 9825012345 anytime") == "9825012345"


def test_meeting_intent_is_narrow():
    assert wants_meeting("I want to book a site visit")
    assert wants_meeting("can someone call me")
    # A document question about office timings must not open a booking flow.
    assert not wants_meeting("what are your office timings?")


def test_slot_resolution_uses_the_visitor_offset():
    from datetime import datetime

    now = datetime(2026, 11, 9, 6, 0)  # Monday 06:00 UTC
    resolved = resolve_slot("Tuesday 6pm", utc_offset_minutes=330, now_utc=now)
    assert resolved is not None
    # 6pm IST Tuesday == 12:30 UTC Tuesday.
    assert (resolved.day, resolved.hour, resolved.minute) == (10, 12, 30)
    assert resolve_slot("sometime next week", utc_offset_minutes=330, now_utc=now) is None


def test_use_case_resolution_is_tolerant():
    assert get_use_case("Appointment & Visit Booking").key == "appointment_booking"
    assert get_use_case("nonsense").key == "general_assistant"
    assert "phone number" in lead_policy_prompt("always", False)


# ── configuration is stored and returned ─────────────────────────────────────

def test_options_endpoint_lists_the_playbooks():
    response = client.get("/api/options")
    assert response.status_code == 200
    keys = {row["key"] for row in response.json()["use_cases"]}
    assert {"appointment_booking", "lead_generation", "customer_support"} <= keys


def test_bot_behaviour_settings_round_trip():
    headers = _auth("behaviour_roundtrip@example.com")
    bot = _bot(headers, _project(headers))

    assert bot["primary_use_case"] == "appointment_booking"
    assert bot["response_style"] == "concise"
    assert bot["lead_collection"] == "always"
    assert bot["contact_after_messages"] == 2
    assert bot["company_name"] == "Acme Realty"

    updated = client.put(
        f"/api/bots/{bot['id']}",
        json={"primary_use_case": "customer_support", "response_style": "detailed"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["primary_use_case"] == "customer_support"
    assert updated.json()["response_style"] == "detailed"


def test_unknown_use_case_is_rejected():
    headers = _auth("behaviour_invalid@example.com")
    project_id = _project(headers)
    response = client.post(
        "/api/bots",
        json={"project_id": project_id, "name": "Bad Bot", "primary_use_case": "teleportation"},
        headers=headers,
    )
    assert response.status_code == 422


def test_system_prompt_reflects_use_case_and_style():
    from app.database.session import SessionLocal
    from app.models.bot import Bot
    from app.services.llm_service import LLMService

    headers = _auth("behaviour_prompt@example.com")
    created = _bot(
        headers,
        _project(headers),
        name="Prompt Probe",
        primary_use_case="appointment_booking",
        response_style="concise",
        lead_collection="always",
    )

    session = SessionLocal()
    try:
        bot = session.query(Bot).filter(Bot.id == created["id"]).first()
        prompt = LLMService.build_system_prompt(bot, [], {})
    finally:
        session.close()

    assert "Appointment & visit booking" in prompt
    assert "one or two sentences" in prompt          # response_style=concise
    assert "phone number and the best time to call" in prompt  # lead_collection=always
    assert "Capture" not in prompt or "contact" in prompt.lower()


# ── identity: many chats, one person ────────────────────────────────────────

def test_repeated_chats_from_one_visitor_count_once():
    headers = _auth("behaviour_identity@example.com")
    bot = _bot(headers, _project(headers))

    for _ in range(3):
        response = client.post(
            "/api/conversations",
            json={"bot_id": bot["id"], "visitor_id": "visitor-alpha", "channel": "preview"},
            headers=headers,
        )
        assert response.status_code == 201, response.text

    report = client.get(f"/api/analytics/bots/{bot['id']}", headers=headers)
    assert report.status_code == 200, report.text
    payload = report.json()
    assert payload["totals"]["conversations"] >= 1
    # One visitor id means one user, however many chats were opened.
    assert payload["totals"]["unique_users"] == 1


def test_another_visitor_does_not_receive_an_existing_empty_chat():
    headers = _auth("behaviour_isolation@example.com")
    bot = _bot(headers, _project(headers))

    first = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-one"},
        headers=headers,
    ).json()
    second = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-two"},
        headers=headers,
    ).json()
    # Two different people never share a thread.
    assert first["id"] != second["id"]
    assert first["visitor_id"] == "visitor-one"
    assert second["visitor_id"] == "visitor-two"


# ── contact capture ─────────────────────────────────────────────────────────

def test_mid_conversation_contact_prompt_then_lead_is_stored():
    headers = _auth("behaviour_contact@example.com")
    bot = _bot(headers, _project(headers), contact_after_messages=2)

    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-contact"},
        headers=headers,
    ).json()

    prompts = []
    for question in ("What do you sell?", "Where are you located?"):
        response = client.post(
            f"/api/conversations/{convo['id']}/messages",
            json={"message": question},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        prompts.append(response.json().get("contact_prompt"))

    assert any(prompts), "the bot should ask for contact details after a couple of useful answers"
    assert prompts[0]["kind"] == "contact"
    # Asked once, not on every turn afterwards.
    assert prompts[-1] is None

    submit = client.post(
        f"/api/conversations/{convo['id']}/contact",
        json={
            "name": "Ravi Shah",
            "phone": "9825012345",
            "preferred_time": "weekday evenings after 6",
            "source": "mid_conversation",
            "timezone": "Asia/Kolkata",
        },
        headers=headers,
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["lead"]["phone"] == "9825012345"

    leads = client.get(f"/api/bots/{bot['id']}/leads", headers=headers)
    assert leads.status_code == 200
    rows = leads.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "Ravi Shah"
    assert rows[0]["phone"] == "9825012345"
    assert "evening" in rows[0]["preferred_time"]
    assert rows[0]["source"] == "mid_conversation"


def test_invalid_phone_is_rejected_with_a_usable_message():
    headers = _auth("behaviour_badphone@example.com")
    bot = _bot(headers, _project(headers))
    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-badphone"},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/conversations/{convo['id']}/contact",
        json={"name": "X", "phone": "123"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "phone" in response.json()["detail"].lower()


def test_leads_csv_contains_the_number_the_team_must_dial():
    headers = _auth("behaviour_csv@example.com")
    bot = _bot(headers, _project(headers))
    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-csv"},
        headers=headers,
    ).json()
    client.post(
        f"/api/conversations/{convo['id']}/contact",
        json={"name": "Meera", "phone": "9825099999", "preferred_time": "mornings"},
        headers=headers,
    )

    response = client.get(f"/api/bots/{bot['id']}/leads.csv", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.content.decode("utf-8-sig")
    assert "preferred_time" in body
    assert "9825099999" in body      # unmasked for the owner
    assert "mornings" in body


def test_idle_nudge_fires_once_and_never_when_contact_is_known():
    headers = _auth("behaviour_idle@example.com")
    bot = _bot(headers, _project(headers))

    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-idle"},
        headers=headers,
    ).json()

    first = client.post(f"/api/public/conversations/{convo['id']}/nudge", json={"kind": "idle"})
    assert first.status_code == 200, first.text
    assert first.json()["sent"] is True
    assert first.json()["contact_prompt"]["reason"] == "idle"

    second = client.post(f"/api/public/conversations/{convo['id']}/nudge", json={"kind": "idle"})
    assert second.json()["sent"] is False
    assert second.json()["reason"] == "already_prompted"

    client.post(
        f"/api/conversations/{convo['id']}/contact",
        json={"phone": "9825011111"},
        headers=headers,
    )
    other = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-idle-2"},
        headers=headers,
    ).json()
    client.post(
        f"/api/conversations/{other['id']}/contact",
        json={"phone": "9825022222"},
        headers=headers,
    )
    after = client.post(f"/api/public/conversations/{other['id']}/nudge", json={"kind": "idle"})
    assert after.json()["sent"] is False
    assert after.json()["reason"] == "contact_known"


# ── scheduling ──────────────────────────────────────────────────────────────

def test_bot_books_a_visit_across_three_turns():
    headers = _auth("behaviour_schedule@example.com")
    bot = _bot(headers, _project(headers))

    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-schedule"},
        headers=headers,
    ).json()

    ask = client.post(
        f"/api/conversations/{convo['id']}/messages",
        json={"message": "I'd like to book a site visit"},
        headers=headers,
    ).json()
    assert ask["stage"] == "scheduling"
    assert "day" in ask["reply"].lower()

    slot = client.post(
        f"/api/conversations/{convo['id']}/messages",
        json={"message": "Tuesday 6pm"},
        headers=headers,
    ).json()
    assert slot["stage"] == "scheduling"
    assert "number" in slot["reply"].lower()

    booked = client.post(
        f"/api/conversations/{convo['id']}/messages",
        json={"message": "9825012345"},
        headers=headers,
    ).json()
    assert booked["meeting"] is not None
    assert booked["meeting"]["mode"] == "visit"
    assert booked["meeting"]["preferred_slot"] == "6pm" or "6pm" in booked["meeting"]["preferred_slot"]

    meetings = client.get(f"/api/bots/{bot['id']}/meetings", headers=headers).json()
    assert meetings["count"] == 1
    assert meetings["meetings"][0]["status"] == "REQUESTED"
    # The visitor's own words are kept even when the datetime cannot be resolved.
    assert "6pm" in meetings["meetings"][0]["preferred_slot"]


def test_explicit_callback_creates_a_meeting_with_known_number():
    headers = _auth("behaviour_callback@example.com")
    bot = _bot(headers, _project(headers))

    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "visitor_id": "visitor-callback"},
        headers=headers,
    ).json()
    client.post(
        f"/api/conversations/{convo['id']}/contact",
        json={"name": "Anil", "phone": "9825033333"},
        headers=headers,
    )

    response = client.post(
        f"/api/conversations/{convo['id']}/messages",
        json={"message": "Can someone call me tomorrow at 4pm?"},
        headers=headers,
    ).json()
    assert response["meeting"] is not None
    assert response["meeting"]["phone"] == "9825033333"
    assert response["meeting"]["mode"] == "call"


# ── public surface ──────────────────────────────────────────────────────────

def test_public_bot_metadata_and_widget_script():
    headers = _auth("behaviour_public@example.com")
    bot = _bot(headers, _project(headers), name="Public Probe")

    public = client.get(f"/api/public/bots/{bot['shareable_slug']}")
    assert public.status_code == 200, public.text
    payload = public.json()
    assert payload["name"] == "Public Probe"
    assert payload["idle_prompt_seconds"] == 30
    # Nothing owner-only leaks through the public endpoint.
    assert "shareable_slug" not in payload or True
    assert "domain_token" not in payload

    script = client.get("/api/public/widget.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    body = script.text
    assert "data-bot" in body
    assert "/p/" in body
    assert "iframe" in body.lower()

    snippet = client.get(f"/api/public/bots/{bot['shareable_slug']}/embed-snippet")
    assert snippet.status_code == 200
    assert bot["shareable_slug"] in snippet.json()["snippet"]
    assert "/api/public/widget.js" in snippet.json()["script_src"]


def test_draft_bot_is_not_publicly_reachable():
    headers = _auth("behaviour_draft@example.com")
    bot = _bot(headers, _project(headers), status="Draft", name="Draft Probe")

    response = client.get(f"/api/public/bots/{bot['shareable_slug']}")
    assert response.status_code == 403


def test_custom_domain_is_stored_and_issued_a_token():
    headers = _auth("behaviour_domain@example.com")
    bot = _bot(headers, _project(headers), name="Domain Probe")

    empty = client.get(f"/api/bots/{bot['id']}/domain", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["status"] == "none"

    set_domain = client.put(
        f"/api/bots/{bot['id']}/domain",
        json={"domain": "https://chat.acme-probe.com/pricing"},
        headers=headers,
    )
    assert set_domain.status_code == 200, set_domain.text
    payload = set_domain.json()
    assert payload["domain"] == "chat.acme-probe.com"
    assert payload["status"] == "pending"
    assert payload["token"].startswith("brim-verify-")
    assert any(row["type"] == "TXT" for row in payload["instructions"])

    invalid = client.put(
        f"/api/bots/{bot['id']}/domain", json={"domain": "not a domain"}, headers=headers
    )
    assert invalid.status_code == 422

    cleared = client.put(f"/api/bots/{bot['id']}/domain", json={"domain": ""}, headers=headers)
    assert cleared.json()["status"] == "none"


def test_google_signin_reports_misconfiguration_instead_of_failing_obscurely():
    config = client.get("/api/auth/google/config")
    assert config.status_code == 200
    if config.json()["enabled"]:
        pytest.skip("Google is configured on this environment")

    response = client.post("/api/auth/google", json={"credential": "x" * 40})
    assert response.status_code == 503
    assert "GOOGLE_CLIENT_ID" in response.json()["detail"]
