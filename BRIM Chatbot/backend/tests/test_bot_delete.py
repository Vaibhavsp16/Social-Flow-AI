"""Deleting a bot must work after it has captured a lead.

The live deployment returned HTTP 500 on delete because the leads table on that database was
created before ``ondelete="CASCADE"`` was declared, and schema repair only adds columns. Deleting
children explicitly removes the dependency on the physical constraint.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _account(suffix: str):
    headers = None
    signup = client.post(
        "/api/auth/signup",
        json={
            "name": f"Delete Check {suffix}",
            "email": f"delete_check_{suffix}@example.com",
            "password": "Password123!",
        },
    )
    if signup.status_code in (200, 201):
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    else:
        login = client.post(
            "/api/auth/login",
            json={"email": f"delete_check_{suffix}@example.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers


def _bot(headers, suffix: str):
    project = client.post(
        "/api/projects",
        json={"name": f"Delete Project {suffix}", "industry": "Real Estate"},
        headers=headers,
    )
    assert project.status_code in (200, 201), project.text
    bot = client.post(
        "/api/bots",
        json={
            "project_id": project.json()["id"],
            "name": f"Delete Bot {suffix}",
            "language": "English",
            "personality": "Concise",
            "primary_use_case": "appointment_booking",
            "lead_collection": "always",
        },
        headers=headers,
    )
    assert bot.status_code in (200, 201), bot.text
    return project.json()["id"], bot.json()


def test_bot_with_a_lead_and_meeting_can_be_deleted():
    suffix = "withdata"
    headers = _account(suffix)
    project_id, bot = _bot(headers, suffix)

    convo = client.post(
        "/api/public/conversations/" + bot["shareable_slug"],
        json={"visitor_id": "delete-check", "channel": "web"},
    )
    assert convo.status_code in (200, 201), convo.text
    convo_id = convo.json()["id"]

    # A lead, via the contact card the chat shows.
    contact = client.post(
        f"/api/public/conversations/{convo_id}/contact",
        json={"name": "Delete Tester", "phone": "98250 12345", "preferred_time": "Evenings"},
    )
    assert contact.status_code == 200, contact.text

    # And a meeting.
    client.post(f"/api/public/conversations/{convo_id}/messages", json={"message": "Can I book a site visit?"})
    client.post(f"/api/public/conversations/{convo_id}/messages", json={"message": "Saturday 11am"})

    deleted = client.delete(f"/api/bots/{bot['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["id"] == bot["id"]

    # Gone, along with its children.
    assert client.get(f"/api/bots/{bot['id']}", headers=headers).status_code == 404
    leads = client.get(f"/api/bots/{bot['id']}/leads", headers=headers)
    assert leads.status_code in (403, 404), "leads survived the bot"


def test_deleting_a_bot_twice_is_a_clean_404():
    suffix = "twice"
    headers = _account(suffix)
    _, bot = _bot(headers, suffix)

    assert client.delete(f"/api/bots/{bot['id']}", headers=headers).status_code == 200
    again = client.delete(f"/api/bots/{bot['id']}", headers=headers)
    assert again.status_code == 404
