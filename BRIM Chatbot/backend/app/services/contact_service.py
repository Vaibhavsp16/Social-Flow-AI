"""Contact capture: parsing details out of a chat, storing them, and exporting them.

Two things matter here and both were absent before:

1. **A phone number is worth nothing without a time to call.** Every captured lead records the
   preferred contact time when the visitor gave one.
2. **One person is one lead.** Submitting details twice in the same conversation updates the row
   instead of creating a duplicate the sales team has to reconcile.
"""

import csv
import io
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.lead import Lead, LeadStatus
from app.models.meeting import Meeting


# ── Parsing ───────────────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r"(?<!\d)(?:\+?(\d{1,3})[\s.-]?)?(\d{6,14})(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# A caller is only useful at a time the person actually named. These are the phrases the chat is
# likely to receive; the match is returned verbatim so the business sees the visitor's own words.
_TIME_PATTERNS = (
    r"any\s?time",
    r"morning[s]?",
    r"afternoon[s]?",
    r"evening[s]?",
    r"night[s]?",
    r"(?:after|before|around|by)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?",
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:-|to|–)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)",
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)",
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day",
    r"tomorrow",
    r"today",
    r"this\s+(?:week|weekend|month)",
    r"next\s+(?:week|weekend|month)",
    r"weekend[s]?",
    r"weekday[s]?",
    r"lunch\s?time",
    r"office\s?hours",
)
_TIME_RE = re.compile(r"\b(?:" + "|".join(_TIME_PATTERNS) + r")\b", re.IGNORECASE)

# Words that are never somebody's name when they appear alone in "my name is X".
_NAME_STOPWORDS = {
    "yes", "no", "ok", "okay", "sure", "hi", "hello", "hey", "thanks", "thank", "you",
    "please", "skip", "later", "here", "this", "that", "it", "me", "not", "call", "email",
}

_SKIP_WORDS = {"skip", "no", "none", "nope", "not now", "later", "na"}


def normalise_phone(raw: str | None) -> Optional[str]:
    """Return a compact dialable number, or None when the text is not a usable phone number.

    Accepts the shapes people actually type: ``+91 98250 12345``, ``9825012345``, ``(079) 1234-5678``.
    Rejects digit runs long enough to be an order number or a budget.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 7 or len(digits) > 15:
        return None
    # A 10-digit local number that begins with 0 still needs the trunk zero dropped.
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return f"+{digits}" if len(digits) > 10 else digits


def extract_phone(text: str) -> Optional[str]:
    if not text:
        return None
    # Try the explicit "+cc ..." form first so the country code is not split off.
    plus = re.search(r"\+\d[\d\s.-]{6,}\d", text)
    if plus:
        candidate = normalise_phone(plus.group(0))
        if candidate:
            return candidate
    # Numbers written the way people actually type them: "98250 12345", "98250-12345". The
    # separator-tolerant pass has to come before the contiguous one, and it demands 10-13 digits so
    # a short run like a price or a year cannot be mistaken for a phone number.
    separated = re.search(r"(?<![\d+])(\+?\d[\d\s.\-]{7,16}\d)(?!\d)", text)
    if separated:
        digits = re.sub(r"\D", "", separated.group(1))
        if 10 <= len(digits) <= 13:
            candidate = normalise_phone(separated.group(1))
            if candidate:
                return candidate

    for match in _PHONE_RE.finditer(text):
        candidate = normalise_phone(match.group(0))
        if candidate and len(re.sub(r"\D", "", candidate)) >= 7:
            return candidate
    return None


def extract_email(text: str) -> Optional[str]:
    if not text:
        return None
    match = _EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


def extract_preferred_time(text: str) -> Optional[str]:
    """The phrase in which the visitor named a convenient time, verbatim.

    "tomorrow evening" and "Tuesday 6pm" are one slot, not two. Taking only the first regex match
    recorded "tomorrow" and threw away the part the business needs, so adjacent hints are merged
    when they are close enough to be the same phrase.
    """
    if not text:
        return None
    matches = list(_TIME_RE.finditer(text))
    if not matches:
        return None

    start, end = matches[0].start(), matches[0].end()
    for match in matches[1:]:
        # Only merge hints that read as one phrase ("Tuesday at 6pm", "weekday evenings").
        if match.start() - end > 16:
            break
        end = match.end()
    return text[start:end].strip(" ,.;")


def extract_name(text: str) -> Optional[str]:
    """Pull a name out of "I'm Ravi" / "my name is Ravi Shah" / a bare name reply."""
    if not text:
        return None
    cleaned = text.strip().strip(".,!")
    patterns = (
        r"(?:my name is|i am|i'm|im|this is|name is)\s+([A-Za-z][A-Za-z' .-]{1,60})",
        r"^([A-Z][A-Za-z'.-]*(?:\s+[A-Z][A-Za-z'.-]*){0,2})$",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" .")
        words = candidate.split()
        if not 1 <= len(words) <= 4:
            continue
        if words[0].lower() in _NAME_STOPWORDS:
            continue
        if len(candidate) < 2:
            continue
        return candidate.title()
    return None


def is_skip(text: str | None) -> bool:
    return (text or "").strip().lower() in _SKIP_WORDS


def looks_like_contact_submission(text: str) -> bool:
    """True when a single message already carries a phone (or an email) to save."""
    return bool(extract_phone(text) or extract_email(text))


# ── Persistence ───────────────────────────────────────────────────────────────

def find_lead_for_conversation(db: Session, conversation_id: Optional[int]) -> Optional[Lead]:
    if not conversation_id:
        return None
    return (
        db.query(Lead)
        .filter(Lead.conversation_id == conversation_id)
        .order_by(Lead.id.desc())
        .first()
    )


def upsert_lead(
    db: Session,
    bot: Bot,
    conversation: Optional[Conversation],
    *,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    preferred_contact: Optional[str] = None,
    preferred_time: Optional[str] = None,
    timezone: Optional[str] = None,
    requirements: Optional[str] = None,
    intent: Optional[str] = None,
    location: Optional[str] = None,
    budget_max: Optional[int] = None,
    meeting_requested: bool = False,
    notes: Optional[str] = None,
    source: str = "chatbot",
) -> Lead:
    """Create or update the lead for this conversation.

    Only non-empty values overwrite existing fields, so a later nudge that collects just a time
    cannot wipe the phone number captured earlier.
    """
    lead = find_lead_for_conversation(db, conversation.id if conversation else None)

    if lead is None:
        lead = Lead(
            bot_id=bot.id,
            conversation_id=conversation.id if conversation else None,
            name=(name or "Website visitor").strip()[:120],
            phone=phone or "",
            email=email,
            preferred_contact=preferred_contact or "Phone",
            preferred_time=preferred_time,
            timezone=timezone,
            requirements=requirements,
            intent=intent,
            location=location,
            budget_max=budget_max,
            meeting_requested=meeting_requested,
            notes=notes,
            status=LeadStatus.NEW.value,
            source=source,
        )
        db.add(lead)
        db.flush()
        return lead

    if name:
        lead.name = name.strip()[:120]
    if phone:
        lead.phone = phone
    if email:
        lead.email = email
    if preferred_contact:
        lead.preferred_contact = preferred_contact
    if preferred_time:
        lead.preferred_time = preferred_time
    if timezone:
        lead.timezone = timezone
    if requirements:
        lead.requirements = requirements
    if intent:
        lead.intent = intent
    if location:
        lead.location = location
    if budget_max:
        lead.budget_max = budget_max
    if meeting_requested:
        lead.meeting_requested = True
    if notes:
        lead.notes = ((lead.notes or "") + "\n" + notes).strip()
    # Keep the earliest attributable source: the nudge that finally worked is useful, but knowing
    # the enquiry started as a mid-conversation prompt is more so.
    if lead.source in (None, "", "chatbot") and source:
        lead.source = source
    db.flush()
    return lead


def lead_payload(lead: Optional[Lead]) -> Optional[Dict[str, Any]]:
    if not lead:
        return None
    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "preferred_contact": lead.preferred_contact,
        "preferred_time": lead.preferred_time,
        "conversation_id": lead.conversation_id,
    }


# ── Export ────────────────────────────────────────────────────────────────────

LEAD_CSV_COLUMNS = [
    "lead_id", "created_at", "bot", "name", "phone", "email", "preferred_contact",
    "preferred_time", "timezone", "intent", "location", "budget_max", "requirements",
    "meeting_requested", "meeting_slot", "meeting_status", "status", "source", "conversation_id",
]


def leads_csv(
    db: Session,
    *,
    bot_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Tuple[str, str]:
    """Leads as CSV, with the numbers the business actually needs to call people.

    Deliberately unmasked for the owning business: this export exists so someone can ring the
    customer. Admin-scope exports mask contact details in ``reporting_service`` and stay that way.
    """
    from app.models.project import Project
    from app.services.analytics_service import parse_window

    window_start, window_end = parse_window(start, end)

    query = db.query(Lead).filter(
        Lead.created_at >= window_start, Lead.created_at <= window_end
    )
    if bot_id is not None:
        query = query.filter(Lead.bot_id == bot_id)
    if user_id is not None:
        query = query.join(Bot, Bot.id == Lead.bot_id).join(
            Project, Project.id == Bot.project_id
        ).filter(Project.user_id == user_id)

    leads: List[Lead] = query.order_by(Lead.created_at.desc()).all()
    bot_names = {
        row.id: row.name
        for row in db.query(Bot).filter(Bot.id.in_({lead.bot_id for lead in leads} or {-1})).all()
    }

    meetings_by_lead: Dict[int, Meeting] = {}
    lead_ids = [lead.id for lead in leads]
    if lead_ids:
        for meeting in (
            db.query(Meeting)
            .filter(Meeting.lead_id.in_(lead_ids))
            .order_by(Meeting.id.desc())
            .all()
        ):
            meetings_by_lead.setdefault(meeting.lead_id, meeting)

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(LEAD_CSV_COLUMNS)
    for lead in leads:
        meeting = meetings_by_lead.get(lead.id)
        writer.writerow([
            lead.id,
            lead.created_at.isoformat() if lead.created_at else "",
            bot_names.get(lead.bot_id, ""),
            lead.name,
            lead.phone,
            lead.email or "",
            lead.preferred_contact,
            lead.preferred_time or "",
            lead.timezone or "",
            lead.intent or "",
            lead.location or "",
            lead.budget_max or "",
            (lead.requirements or "").replace("\n", " "),
            "yes" if lead.meeting_requested else "no",
            (meeting.preferred_slot or "") if meeting else "",
            (meeting.status or "") if meeting else "",
            lead.status,
            lead.source,
            lead.conversation_id or "",
        ])

    stamp = (end or datetime.now().date()).isoformat()
    return buffer.getvalue(), f"brim_leads_{stamp}.csv"
