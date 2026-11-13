"""Arranging a call or a visit from inside the chat.

Deterministic on purpose. The visitor's request has to end up as a row the business can act on, and
a language model cannot be trusted to produce a stable slot; so the intent and the slot are parsed
here, and the model only writes the surrounding sentence.

The state machine is small and explicit:

    (no stage) --wants meeting--> ask_slot --slot--> [ask_phone] --phone--> booked

``ask_phone`` is skipped when the conversation already has a phone number, which is the common case
after a contact prompt.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.messages import translate
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.meeting import Meeting, MeetingMode, MeetingStatus
from app.services.contact_service import (
    extract_phone,
    extract_preferred_time,
    find_lead_for_conversation,
    upsert_lead,
)

# Asking to be contacted is scheduling intent, not a document question. Kept narrow so "what are
# your office timings?" does not open a booking flow.
_MEETING_PATTERNS = (
    r"\b(?:book|schedule|arrange|set up|fix)\b.{0,24}\b(?:meeting|appointment|call|visit|demo|slot|time)\b",
    r"\b(?:site|office|store|factory|campus)\s+visit\b",
    r"\b(?:can|could|would)\s+(?:i|we)\s+(?:visit|come over|drop by|meet)\b",
    r"\b(?:speak|talk)\s+(?:to|with)\s+(?:someone|an advisor|a human|your team)\b",
    r"\b(?:want|need|like)\s+(?:a\s+)?(?:call|callback|call back)\b",
    # "can someone call me", "please have your team contact me" — the plain request to be reached.
    r"\b(?:can|could|would|will)\s+(?:someone|somebody|your\s+team|you)\s+(?:please\s+)?(?:call|contact|reach|ring)\b",
    r"\b(?:please\s+)?(?:call|contact|ring)\s+me\s*(?:back|at|on|tomorrow|today|in\s+the)?\b",
    r"\bhave\s+(?:someone|your\s+team)\s+(?:call|contact)\b",
    r"\b(?:book|reserve)\s+(?:a\s+)?(?:plot|unit|flat|site|visit|ticket)\b",
    r"\bappointment\b",
    r"\bcallback\b",
)

_MODE_HINTS = (
    (r"\b(?:visit|site visit|come over|drop by|office|store|factory|campus)\b", MeetingMode.VISIT.value),
    (r"\b(?:video|zoom|google meet|teams|online)\b", MeetingMode.VIDEO.value),
    (r"\b(?:office|meeting room|in person)\b", MeetingMode.OFFICE.value),
)

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
_TIME_24_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


# "speak to a human" is a handoff, not a booking. Asking those visitors for a day and time is
# exactly backwards — they have already said a person should take over.
_HANDOFF_ONLY = ("human", "real person", "agent", "representative", "customer support")


def wants_meeting(message: str) -> bool:
    text = (message or "").lower()
    if any(word in text for word in _HANDOFF_ONLY):
        return False
    return any(re.search(pattern, text) for pattern in _MEETING_PATTERNS)


def meeting_mode(message: str) -> str:
    text = (message or "").lower()
    for pattern, mode in _MODE_HINTS:
        if re.search(pattern, text):
            return mode
    return MeetingMode.CALL.value


def _hour_minute(text: str) -> Optional[Tuple[int, int]]:
    match = _TIME_RE.search(text or "")
    if match:
        hour = int(match.group(1)) % 12
        minute = int(match.group(2) or 0)
        if match.group(3).lower() == "pm":
            hour += 12
        return hour, minute
    match = _TIME_24_RE.search(text or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    lowered = (text or "").lower()
    if "morning" in lowered:
        return 10, 0
    if "afternoon" in lowered:
        return 15, 0
    if "evening" in lowered:
        return 18, 0
    return None


def _target_date(text: str, now_local: datetime) -> Optional[datetime]:
    lowered = (text or "").lower()
    if "today" in lowered:
        return now_local
    if "tomorrow" in lowered:
        return now_local + timedelta(days=1)
    if "weekend" in lowered:
        days_ahead = (5 - now_local.weekday()) % 7
        return now_local + timedelta(days=days_ahead or 7)
    if "next week" in lowered:
        days_ahead = (7 - now_local.weekday()) % 7 or 7
        return now_local + timedelta(days=days_ahead)
    for name, index in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", lowered):
            days_ahead = (index - now_local.weekday()) % 7
            return now_local + timedelta(days=days_ahead or 7)
    return None


def resolve_slot(
    slot_text: str,
    *,
    utc_offset_minutes: Optional[int] = None,
    now_utc: Optional[datetime] = None,
) -> Optional[datetime]:
    """Turn "Tuesday 6pm" into a naive UTC datetime, or None when the phrase is too vague.

    Returning None is the honest outcome for "sometime next week" — the team confirms, and the raw
    phrase is still stored on the meeting.
    """
    if not slot_text:
        return None
    offset = utc_offset_minutes if utc_offset_minutes is not None else 0
    now_utc = now_utc or datetime.now(timezone.utc).replace(tzinfo=None)
    now_local = now_utc + timedelta(minutes=offset)

    hour_minute = _hour_minute(slot_text)
    target = _target_date(slot_text, now_local)
    if hour_minute is None:
        return None
    if target is None:
        # Only a time was given: today if it is still ahead, otherwise tomorrow.
        target = now_local
    resolved_local = target.replace(hour=hour_minute[0], minute=hour_minute[1], second=0, microsecond=0)
    if resolved_local <= now_local:
        resolved_local += timedelta(days=1)
    return resolved_local - timedelta(minutes=offset)


def ask_slot_reply(bot: Bot, language: str, mode: str) -> str:
    key = "meeting_ask_slot_visit" if mode == MeetingMode.VISIT.value else "meeting_ask_slot"
    return translate(language, key, bot=bot.name)


def book(
    db: Session,
    *,
    bot: Bot,
    conversation: Optional[Conversation],
    state: Dict[str, Any],
    language: str,
    mode: str,
    slot_text: Optional[str],
    phone: Optional[str] = None,
    name: Optional[str] = None,
) -> Tuple[Meeting, str]:
    """Persist the meeting and return the confirmation sentence."""
    existing_lead = find_lead_for_conversation(db, conversation.id if conversation else None)

    lead = upsert_lead(
        db,
        bot,
        conversation,
        name=name or (existing_lead.name if existing_lead else None),
        phone=phone or (existing_lead.phone if existing_lead else None),
        preferred_time=slot_text,
        timezone=state.get("timezone"),
        meeting_requested=True,
        requirements=state.get("requirements_summary"),
        intent=state.get("intent"),
        location=state.get("location"),
        budget_max=state.get("budget_max"),
        source="scheduling",
        notes=f"Meeting requested ({mode}): {slot_text or 'no slot given'}",
    )

    scheduled_for = resolve_slot(
        slot_text or "",
        utc_offset_minutes=state.get("utc_offset_minutes"),
    )
    meeting = Meeting(
        bot_id=bot.id,
        lead_id=lead.id,
        conversation_id=conversation.id if conversation else None,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        mode=mode,
        preferred_slot=slot_text,
        scheduled_for=scheduled_for,
        timezone=state.get("timezone"),
        status=MeetingStatus.REQUESTED.value,
        source="chatbot",
        notes=None,
    )
    db.add(meeting)
    db.flush()

    label = {
        MeetingMode.VISIT.value: "site visit",
        MeetingMode.VIDEO.value: "video call",
        MeetingMode.OFFICE.value: "office meeting",
    }.get(mode, "call")

    if slot_text:
        reply = translate(language, "meeting_booked", slot=slot_text, mode=label)
    else:
        reply = translate(language, "meeting_booked_no_slot", mode=label)
    if lead.phone:
        reply += " " + translate(language, "meeting_reach_on", phone=lead.phone)
    return meeting, reply


def meeting_payload(meeting: Optional[Meeting]) -> Optional[Dict[str, Any]]:
    if not meeting:
        return None
    return {
        "id": meeting.id,
        "mode": meeting.mode,
        "preferred_slot": meeting.preferred_slot,
        "scheduled_for": meeting.scheduled_for.isoformat() if meeting.scheduled_for else None,
        "status": meeting.status,
        "phone": meeting.phone,
    }
