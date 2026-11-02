"""
Context + language phase: detection, greeting decisions, location privacy and multilingual flow.
"""

import json
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.messages import is_refusal
from app.main import app
from app.services.greeting_service import GreetingService
from app.services.holiday_service import HolidayService
from app.services.language_service import LanguageService
from app.services.weather_service import WeatherService

client = TestClient(app)


@pytest.fixture
def account():
    email = f"ctx_{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/api/auth/signup",
        json={"name": "Context Tester", "email": email, "password": "Test@12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_bot(headers, industry="Real Estate", name="Prycoons Advisor"):
    project = client.post(
        "/api/projects",
        json={"name": f"CTX {uuid.uuid4().hex[:6]}", "industry": industry},
        headers=headers,
    ).json()
    return client.post(
        "/api/bots",
        json={"project_id": project["id"], "name": name, "status": "Live"},
        headers=headers,
    ).json()


def send(headers, convo_id, text, language=None):
    payload = {"message": text}
    if language:
        payload["language"] = language
    response = client.post(
        f"/api/conversations/{convo_id}/messages", json=payload, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


# ── Language detection ────────────────────────────────────────────────────────

def test_language_detection_and_normalisation():
    assert LanguageService.detect("I want to buy a 3 BHK flat") == "en"
    assert LanguageService.detect("मुझे 3 बीएचके फ्लैट चाहिए") == "hi"
    assert LanguageService.detect("મને 3 બીએચકે ફ્લેટ જોઈએ છે") == "gu"
    assert LanguageService.detect("मला 3 बीएचके फ्लॅट हवे आहे") == "mr"
    assert LanguageService.detect("mujhe 3 bhk chahiye") == "hi"
    assert LanguageService.detect("mane 3 bhk joiye che") == "gu"
    # Unsupported script falls back to English rather than garbling the reply.
    assert LanguageService.detect("நான் ஒரு வீடு வாங்க விரும்புகிறேன்") == "en"
    assert LanguageService.normalise("hi-IN") == "hi"
    assert LanguageService.normalise("fr-FR") is None


# ── Greeting engine ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "hour,expected",
    [(8, "Good morning"), (14, "Good afternoon"), (18, "Good evening"), (23, "up late")],
)
def test_greeting_time_of_day(monkeypatch, hour, expected):
    monkeypatch.setenv("WEATHER_ENABLED", "false")
    greeting = GreetingService.build(
        "Prycoons", language="en", local_hour=hour, include_engagement=False,
        industry="Real Estate",
    )
    assert greeting["text"].startswith("Welcome to the chat!")
    # One short welcome question only — no intent menu, no personal question.
    assert "What can I do for you today?" in greeting["text"]


def test_non_property_bot_gets_a_neutral_greeting(monkeypatch):
    """An FMCG bot must not introduce itself as a property assistant (screenshot regression)."""
    monkeypatch.setenv("WEATHER_ENABLED", "false")
    greeting = GreetingService.build(
        "BRIM FMCG Assistant", language="en", local_hour=18, include_engagement=False,
        industry="FMCG",
    )
    text = greeting["text"]
    assert "property assistant" not in text.lower()
    assert "buy a home" not in text.lower()
    assert "What can I do for you today?" in text


def test_greeting_holiday_outranks_weather_and_time(monkeypatch):
    monkeypatch.setattr(
        HolidayService,
        "on",
        classmethod(lambda cls, day=None, language="en": {
            "is_holiday": True, "name": "Diwali", "localised_name": "Diwali", "date": "2026-11-08"
        }),
    )
    monkeypatch.setattr(
        WeatherService,
        "get",
        classmethod(lambda cls, city: {
            "available": True, "city": city, "temp_c": 31, "condition": "light rain",
            "notable": True, "summary": "light rain, 31°C",
        }),
    )
    greeting = GreetingService.build(
        "Prycoons", language="en", city="Ahmedabad", local_hour=18, include_engagement=False
    )
    assert greeting["context"]["holiday"] == "Diwali"


def test_greeting_weather_available_and_unavailable(monkeypatch):
    monkeypatch.setenv("WEATHER_MENTION_PROBABILITY", "1.0")
    monkeypatch.setattr(
        WeatherService, "get",
        classmethod(lambda cls, city: {
            "available": True, "city": city, "temp_c": 31, "condition": "light rain",
            "notable": False, "summary": "light rain, 31°C",
        }),
    )
    greeting = GreetingService.build(
        "Prycoons", language="en", city="Ahmedabad", local_hour=10, include_engagement=False
    )
    # Weather is still resolved for context, but no longer appended to the opening line.
    assert greeting["context"]["weather_available"] is True
    assert "light rain" not in greeting["text"]

    monkeypatch.setattr(
        WeatherService, "get",
        classmethod(lambda cls, city: {"available": False, "city": city, "summary": None}),
    )
    fallback = GreetingService.build(
        "Prycoons", language="en", city="Ahmedabad", local_hour=10, include_engagement=False
    )
    assert "light rain" not in fallback["text"]
    assert "Welcome to the chat!" in fallback["text"]


def test_greeting_without_location_still_works(monkeypatch):
    monkeypatch.setenv("WEATHER_ENABLED", "false")
    greeting = GreetingService.build(
        "Prycoons", language="en", city=None, include_engagement=False
    )
    assert greeting["text"]
    assert greeting["context"]["city"] is None


def test_greeting_in_each_language():
    assert "चैट में आपका स्वागत है!" in GreetingService.build(
        "Prycoons", language="hi", local_hour=8, include_engagement=False
    )["text"]
    assert "ચેટમાં આપનું સ્વાગત છે!" in GreetingService.build(
        "Prycoons", language="gu", local_hour=8, include_engagement=False
    )["text"]
    assert "चॅटमध्ये आपले स्वागत आहे!" in GreetingService.build(
        "Prycoons", language="mr", local_hour=8, include_engagement=False
    )["text"]


def test_holiday_calendar_is_configurable():
    diwali = HolidayService.on(day=date(2026, 11, 8), language="hi")
    assert diwali["is_holiday"] and diwali["name"] == "Diwali"
    assert diwali["localised_name"] == "दिवाली"
    assert HolidayService.on(day=date(2026, 7, 15))["is_holiday"] is False


# ── API ───────────────────────────────────────────────────────────────────────

def test_languages_and_greeting_endpoints(account):
    languages = client.get("/api/context/languages").json()
    assert {row["code"] for row in languages["languages"]} == {"en", "hi", "gu", "mr"}

    morning = client.post(
        "/api/context/greeting", json={"language": "hi", "local_hour": 9}
    ).json()
    assert "चैट में आपका स्वागत है!" in morning["text"]
    assert morning["context"]["time_of_day"] == "morning"

    # No location provided — the greeting must still be produced.
    no_location = client.post("/api/context/greeting", json={"language": "en"}).json()
    assert no_location["text"]
    assert no_location["context"]["city"] is None


def test_conversation_greeting_is_stored_with_coarse_location_only(account):
    bot = make_bot(account)
    convo = client.post(
        "/api/conversations",
        json={
            "bot_id": bot["id"],
            "language": "gu",
            "city": "Ahmedabad",
            "region": "Gujarat",
            "local_hour": 20,
            "location_granted": True,
        },
        headers=account,
    ).json()

    assert convo["messages"], "a greeting message should be stored"
    greeting = convo["messages"][0]
    assert greeting["sender"] == "ASSISTANT"
    assert "હું આપની શું મદદ કરી શકું?" in greeting["content"]

    state_raw = convo["conversation_state"]
    assert "Ahmedabad" in state_raw
    for forbidden in ("latitude", "longitude", "lat\"", "lng", "coords"):
        assert forbidden not in state_raw.lower()


# ── Multilingual flow ────────────────────────────────────────────────────────

def test_greeting_is_not_repeated_after_hi(account):
    """The stored greeting is the opener; saying "Hi" must not replay it."""
    bot = make_bot(account)
    convo = client.post(
        "/api/conversations",
        json={"bot_id": bot["id"], "language": "en", "local_hour": 10},
        headers=account,
    ).json()
    reply = send(account, convo["id"], "Hi")
    assert reply["reply"].count("?") <= 1
    assert "buy a home" not in reply["reply"]


def test_hindi_flow_keeps_state_and_answers_in_hindi(account):
    bot = make_bot(account)
    convo = client.post("/api/conversations", json={"bot_id": bot["id"]}, headers=account).json()

    first = send(account, convo["id"], "मुझे 3 बीएचके फ्लैट चाहिए अंबली में")
    assert first["language"] == "hi"
    assert first["conversation_state"]["bhk"] == 3
    assert first["conversation_state"]["location"] == "Ambli"
    assert any("\u0900" <= char <= "\u097F" for char in first["reply"])

    second = send(account, convo["id"], "बजट 2 करोड़ है")
    assert second["language"] == "hi"
    assert second["stage"] == "shortlist"
    assert second["properties"], "Hindi requirements should still produce a shortlist"
    assert any("\u0900" <= char <= "\u097F" for char in second["reply"])


def test_english_after_hindi_keeps_requirements(account):
    bot = make_bot(account)
    convo = client.post("/api/conversations", json={"bot_id": bot["id"]}, headers=account).json()

    send(account, convo["id"], "मुझे 3 बीएचके फ्लैट चाहिए अंबली में")
    switched = send(account, convo["id"], "Budget is around 2 crore")

    assert switched["language"] == "en"
    assert switched["conversation_state"]["bhk"] == 3
    assert switched["conversation_state"]["location"] == "Ambli"
    assert switched["stage"] == "shortlist"
    assert switched["properties"]


def test_explicit_language_selection(account):
    bot = make_bot(account, industry="Healthcare", name="Clinic Assistant")
    convo = client.post("/api/conversations", json={"bot_id": bot["id"]}, headers=account).json()
    reply = send(account, convo["id"], "What are your timings?", language="hi")
    assert reply["language"] == "hi"
    assert any("\u0900" <= char <= "\u097F" for char in reply["reply"])


def test_refusal_is_localised(account):
    bot = make_bot(account, industry="Healthcare", name="Clinic Assistant")
    convo = client.post("/api/conversations", json={"bot_id": bot["id"]}, headers=account).json()
    reply = send(account, convo["id"], "मुझे क्लिनिक के बारे में बताइए")
    assert reply["language"] == "hi"
    assert is_refusal(reply["reply"])
    assert any("\u0900" <= char <= "\u097F" for char in reply["reply"])
    assert reply["sources"] == []
