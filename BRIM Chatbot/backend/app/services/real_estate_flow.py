"""
Prycoons real-estate conversation flow.

    greeting → intent → requirements → shortlist → lead capture → confirmation → handoff

The flow is a deterministic dialogue manager: it decides which question to ask next, extracts
requirements from free text, and queries the property table. It never invents a listing — the
shortlist text is generated from rows returned by PropertyService. Free-form knowledge questions
are delegated back to the RAG pipeline through the ``knowledge_answer`` callback.

Everything lives in ``conversation_state`` (JSON), so a page reload resumes mid-flow.
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.messages import is_refusal, translate
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.property import ListingType
from app.services.greeting_service import GreetingService
from app.services.property_service import PropertyService

logger = logging.getLogger(__name__)

STAGE_GREETING = "greeting"
STAGE_DISCOVER = "discover"
STAGE_SHORTLIST = "shortlist"
STAGE_LEAD = "lead"
STAGE_CONFIRM = "confirm"
STAGE_HANDOFF = "handoff"

KNOWN_AREAS = [
    "ambli", "bopal", "satellite", "sg highway", "gandhinagar", "thaltej",
    "prahlad nagar", "bodakdev", "maninagar", "vastrapur", "chandkheda",
]

AMENITY_WORDS = [
    "pool", "gym", "parking", "garden", "terrace", "balcony", "clubhouse",
    "security", "lift", "playground", "furnished", "cctv", "power backup",
]

# Hindi/Gujarati/Marathi words mapped to the English tokens the extractor already understands,
# so the same slot logic works in every supported language.
LOCALISED_TOKENS = {
    # Areas
    "अंबली": "ambli", "અંબલી": "ambli",
    "बोपल": "bopal", "બોપલ": "bopal",
    "सैटेलाइट": "satellite", "સેટેલાઇટ": "satellite",
    "एसजी हाईवे": "sg highway", "એસજી હાઈવે": "sg highway",
    "गांधीनगर": "gandhinagar", "ગાંધીનગર": "gandhinagar",
    "थलतेज": "thaltej", "થલતેજ": "thaltej",
    "प्रह्लाद नगर": "prahlad nagar", "પ્રહલાદ નગર": "prahlad nagar",
    # BHK and property types
    "बीएचके": "bhk", "બીએચકે": "bhk",
    "बेडरूम": "bedroom", "બેડરૂમ": "bedroom",
    "फ्लैट": "flat", "ફ્લેટ": "flat",
    "अपार्टमेंट": "apartment", "એપાર્ટમેન્ટ": "apartment",
    "विला": "villa", "વિલા": "villa",
    "प्लॉट": "plot", "પ્લોટ": "plot",
    # Intent
    "किराए": "rent", "किराया": "rent", "भाड्याने": "rent", "ભાડે": "rent", "ભાડું": "rent",
    "खरीद": "buy", "ખરીદ": "buy",
    # Budget units
    "करोड़": "crore", "કરોડ": "crore",
    "लाख": "lakh", "લાખ": "lakh",
    # Amenities
    "पूल": "pool", "પૂલ": "pool",
    "जिम": "gym", "જિમ": "gym",
    "पार्किंग": "parking", "પાર્કિંગ": "parking",
    "बगीचा": "garden", "બગીચો": "garden",
}


def _normalise_localised(message: str) -> str:
    text = (message or "").lower()
    for source, target in LOCALISED_TOKENS.items():
        if source in text:
            text = text.replace(source, target)
    return text


AFFIRMATIVE = {"yes", "yeah", "yep", "sure", "ok", "okay", "please", "definitely",
               "go ahead", "sounds good", "why not", "interested", "call me"}
NEGATIVE = {"no", "not now", "later", "nope", "no thanks", "not really"}

LEAD_FIELDS = ["lead_name", "lead_phone", "lead_email", "lead_contact"]
CONTACT_CHOICES = {
    "phone": "Phone", "call": "Phone", "whatsapp": "WhatsApp", "email": "Email",
}


def _numbers_only(value: str) -> str:
    return re.sub(r"[^\d+]", "", value or "")


def _parse_budget(text: str) -> Optional[int]:
    """'2 crore', '85 lakh', '40k', '₹35,000' → rupees (k suffix only for rentals)."""
    lowered = text.lower().replace(",", "")
    crore = re.search(r"(\d+(?:\.\d+)?)\s*(?:cr\b|crore|crores)", lowered)
    if crore:
        return int(float(crore.group(1)) * 10_000_000)
    lakh = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b", lowered)
    if lakh:
        return int(float(lakh.group(1)) * 100_000)
    thousand = re.search(r"(\d+(?:\.\d+)?)\s*(?:k\b|thousand)", lowered)
    if thousand:
        return int(float(thousand.group(1)) * 1_000)
    plain = re.search(r"(?:₹|rs\.?|inr)\s*(\d[\d\s]{3,})", lowered)
    if plain:
        return int(re.sub(r"\s", "", plain.group(1)))
    return None


def extract_slots(message: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Pull property requirements out of a free-text turn. Never clears existing values."""
    text = _normalise_localised(message)
    updates: Dict[str, Any] = {}

    # BHK: "3 bhk", "3bhk", "three bedroom"
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    bhk_match = re.search(r"\b(\d)\s*(?:bhk|b\.h\.k|bedroom|bed\b)", text)
    if bhk_match:
        updates["bhk"] = int(bhk_match.group(1))
    else:
        for word, number in words.items():
            if f"{word} bedroom" in text or f"{word} bhk" in text:
                updates["bhk"] = number
                break

    # Property type
    type_map = {
        "apartment": "Apartment", "flat": "Apartment", "villa": "Villa",
        "bungalow": "Villa", "penthouse": "Penthouse", "plot": "Plot", "land": "Plot",
    }
    for word, canonical in type_map.items():
        if re.search(rf"\b{word}s?\b", text):
            updates["property_type"] = canonical
            break

    budget = _parse_budget(text)
    if budget:
        updates["budget_max"] = budget

    amenities = [amenity for amenity in AMENITY_WORDS if amenity in text]
    if amenities:
        existing = state.get("amenities", []) or []
        updates["amenities"] = sorted(set(existing) | set(amenities))

    for area in KNOWN_AREAS:
        if area in text:
            updates["location"] = area.title()
            break
    if "location" not in updates:
        location_match = re.search(
            r"\b(?:in|at|near|around)\s+([a-z][a-z\s]{2,20}?)\s*(?:,|\.|$|\bwith\b|\bfor\b|\bunder\b)",
            text,
        )
        if location_match:
            raw = location_match.group(1).strip()
            noise = {
                "the", "our", "your", "this", "that", "a", "an", "any", "all", "town", "city",
                "what", "what's", "which", "where", "how", "when", "who", "something", "area",
                "good", "nice", "budget", "same", "nearby", "around",
            }
            # Require a proper noun: "in Ambli" is a location, "at what's available" is not.
            if raw[:1].isupper() and raw.split()[0].lower() not in noise and len(raw) <= 24:
                updates["location"] = raw.title()

    if any(word in text for word in ["immediately", "ready to move", "asap", "this month"]):
        updates["timeline"] = "immediate"
    elif any(word in text for word in ["next year", "6 months", "six months", "later this year"]):
        updates["timeline"] = "6-12 months"
    elif any(word in text for word in ["investment", "invest", "rental income", "resale"]):
        updates["purpose"] = "investment"
    elif any(word in text for word in ["family", "self use", "own use", "stay"]):
        updates["purpose"] = "family home"

    return updates


class RealEstateFlow:

    # ── Public entry point ────────────────────────────────────────────────────

    @classmethod
    def should_handle(cls, message: str, state: Dict[str, Any]) -> bool:
        """
        True only when the visitor is actually talking about property.

        The flow used to take every message, so a document question got answered with "how many
        bedrooms do you need?". Knowledge questions now stay with retrieval; the workflow only
        engages on explicit buying/renting/browsing language, or while it is mid-lead-capture.
        """
        if state.get("lead_pending") or state.get("stage") in {STAGE_LEAD, STAGE_CONFIRM}:
            return True
        if state.get("stage") == STAGE_SHORTLIST and cls._is_affirmative(message):
            return True
        text = _normalise_localised(message or "")

        markers = (
            "buy", "buying", "rent", "rental", "lease", "purchase", "invest",
            "show me", "shortlist", "crore", "lakh",
            "what is available", "what's available", "give me what", "options for",
        )
        if any(marker in text for marker in markers):
            return True
        # A bare "budget" is not property intent: "which channel gets the largest budget share"
        # is a document question. Only a budget with an amount is.
        if re.search(
            r"budget\s*(?:is|of|around|under|below|upto|up to|max)?\s*[\u20b9$]?\s*\d",
            text,
        ) or "my budget" in text:
            return True
        # "3 bhk", "5 BHK", "2 bedrooms" in any supported script (normalised above).
        if re.search(r"\b\d+\s*(?:bhk|bedroom|bedrooms)\b", text):
            return True

        # A requirement question is outstanding, so a short answer like "In Ambli" or "under 2
        # crore" continues the workflow. An explicit question goes to the knowledge base
        # instead — that is what keeps the conversation from feeling scripted.
        if state.get("asked") and not cls._looks_like_question(message):
            return True
        return False

    QUESTION_RE = re.compile(
        r"\b(what|who|whom|whose|when|where|which|why|how|explain|describe|tell me|"
        r"do you have|does it|is there|are there|can you share|list)\b",
        re.IGNORECASE,
    )

    @classmethod
    def _looks_like_question(cls, message: str) -> bool:
        text = (message or "").strip()
        if text.endswith("?"):
            return True
        return bool(cls.QUESTION_RE.search(_normalise_localised(text)))

    @classmethod
    def handle(
        cls,
        db: Session,
        bot: Bot,
        conversation: Conversation,
        message: str,
        state: Dict[str, Any],
        knowledge_answer: Optional[Callable[[str], Tuple[str, List[Dict[str, Any]]]]] = None,
    ) -> Dict[str, Any]:
        """
        Process one user turn.

        Returns: reply, state, properties, lead, handoff, stage.
        ``knowledge_answer`` lets the caller answer document questions mid-flow; it returns
        (reply, citations).
        """
        PropertyService.ensure_seeded(db, bot.id)

        state.setdefault("stage", STAGE_GREETING)
        state.setdefault("asked", [])
        lang = state.get("language") or "en"
        if state.get("intent") == "human_assistance":
            state["intent"] = None
        # Resume the intent from the stored conversation when the state blob lost it, so a
        # callback request does not reset a buying conversation to browsing.
        stored_intent = getattr(conversation, "intent", None)
        if not state.get("intent") and stored_intent in {"buying", "renting", "browsing"}:
            state["intent"] = stored_intent
        intent = cls._resolve_intent(message, state)
        state["intent"] = intent
        updates = extract_slots(message, state)
        for key, value in updates.items():
            state[key] = value

        properties: List[Dict[str, Any]] = []
        citations: List[Dict[str, Any]] = []

        # 1. Lead collection in progress: the next message answers the pending field.
        if state.get("lead_pending"):
            result = cls._capture_lead_field(db, bot, conversation, message, state)
            if result:
                return result

        # 2. Explicit handoff.
        if intent == "human_assistance":
            reply = translate(lang, "handoff")
            state["stage"] = STAGE_HANDOFF
            state["handoff_reason"] = "user_requested"
            return cls._result(reply, state, handoff=True)

        # 3. Lead offer accepted. Before the detail and question branches: "the first one looks
        #    good, can someone call me?" contains both "first" and a question mark, but is an
        #    acceptance of the advisor offer — unless the visitor explicitly asks for detail.
        if (
            state.get("lead_offered")
            and cls._is_affirmative(message)
            and not cls._wants_detail(message)
        ):
            state["lead_offered"] = False
            state["stage"] = STAGE_LEAD
            state["lead_pending"] = "lead_name"
            return cls._result(translate(lang, "lead_start"), state)
        if state.get("lead_offered") and cls._is_negative(message):
            state["lead_offered"] = False
            state["stage"] = STAGE_SHORTLIST
            return cls._result(
                translate(lang, "lead_declined"),
                state,
                properties=cls._last_shortlist(state),
            )

        # 4. Details about a property. Checked before the generic question branch so
        #    "tell me about the first one" comes from the shortlist and "price of the Thaltej
        #    one" is looked up in the catalogue, not answered from the documents.
        detail = cls._describe_selected_property(message, state, lang)
        if detail:
            return cls._result(detail, state, properties=cls._last_shortlist(state))

        if cls._wants_detail(message) or "price" in message.lower() or "cost" in message.lower():
            named = cls._lookup_property(db, bot.id, message)
            if named:
                return cls._result(
                    cls._property_sentence(named, lang), state, properties=[named]
                )

        # 5. A document/business question mid-flow: answer it, then return to the flow.
        # A question is a knowledge question unless it is a property request ("do you have
        # 3 BHK in Ambli?"). Without this, any question mentioning a place was read as a
        # location answer and the bot replied with the next requirement prompt instead.
        asks_about_knowledge = cls._is_question(message) and not re.search(
            r"\b(?:do|does)\s+(?:you|u)\s+(?:have|offer)\b", message.lower()
        )
        if asks_about_knowledge and (not updates or not cls._states_intent(message)):
            if knowledge_answer is not None:
                answer, citations = knowledge_answer(message)
                if is_refusal(answer):
                    # Never tack "shall we talk about your requirements?" onto a refusal.
                    return cls._result(answer, state, citations=citations)
                # Answer the question and stop there. Appending the next requirement question
                # made every reply feel like a script.
                if state.get("stage") == STAGE_GREETING:
                    state["stage"] = STAGE_DISCOVER
                return cls._result(answer, state, citations=citations)

        # 6. First turn: greet and ask what they are after — unless the first message already
        #    answers that ("just looking", "I want to rent"), in which case get straight to it.
        if (
            state["stage"] == STAGE_GREETING
            and not cls._has_requirements(state)
            and not cls._states_intent(message)
        ):
            state["stage"] = STAGE_DISCOVER
            # A conversation created through the API already carries a contextual greeting
            # (greeting_decision is set by ConversationService._add_greeting). Repeating the
            # whole greeting after "Hi" reads like a loop, so only the intent question follows.
            if state.get("greeting_decision"):
                return cls._result(translate(lang, "ask_intent"), state)
            greeting = GreetingService.build(
                bot_name=bot.name,
                industry="Real Estate",
                language=lang,
                include_engagement=False,
                seed=f"conversation-{conversation.id if conversation else 'new'}",
            )
            state["greeting_context"] = greeting["context"]
            return cls._result(greeting["text"], state)

        # 7. Browse-only mode: show options without pushing a lead.
        if intent == "browsing" and not cls._has_requirements(state):
            state["stage"] = STAGE_SHORTLIST
            properties = PropertyService.search(
                db, bot.id, listing_type=ListingType.SALE.value, limit=3
            )
            reply = (
                f"{translate(lang, 'browse_intro')}\n\n"
                + PropertyService.describe_shortlist(properties, "buying", lang)
                + f"\n\n{translate(lang, 'browse_hint')}"
            )
            state["last_shortlist"] = [p["property_id"] for p in properties]
            return cls._result(reply, state, properties=properties)

        # 8. Enough information for a shortlist?
        if cls._ready_for_shortlist(state):
            properties = PropertyService.search(
                db,
                bot.id,
                listing_type=ListingType.RENT.value if intent == "renting" else ListingType.SALE.value,
                location=state.get("location"),
                property_type=state.get("property_type"),
                bhk=state.get("bhk"),
                budget_max=state.get("budget_max"),
                amenities=state.get("amenities"),
                limit=3,
            )
            state["stage"] = STAGE_SHORTLIST
            state["last_shortlist"] = [p["property_id"] for p in properties]
            reply = PropertyService.describe_shortlist(properties, intent, lang)

            # Never claim a match that isn't one: if the requested area produced nothing, say so.
            requested_area = (state.get("location") or "").lower()
            if requested_area and properties and not any(
                requested_area in (p["location"] or "").lower()
                or (p["location"] or "").lower() in requested_area
                for p in properties
            ):
                criteria = " ".join(
                    part for part in [
                        f"{state.get('bhk')} BHK" if state.get("bhk") else "",
                        (state.get("property_type") or "").lower(),
                    ] if part
                ).strip()
                reply = translate(
                    lang, "no_match_area", criteria=criteria or "a match", area=state.get("location")
                ) + "\n\n" + reply

            if properties:
                state["lead_offered"] = True
                reply += "\n\n" + translate(lang, "advisor_offer")
            else:
                reply += "\n\n" + translate(lang, "widen_offer")
                state["lead_offered"] = True
            return cls._result(reply, state, properties=properties)

        # 9. Keep qualifying, one question per turn.
        next_slot = cls._next_slot(state)
        if next_slot is None:
            # Everything asked and still no shortlist: fall back to browsing.
            state["stage"] = STAGE_SHORTLIST
            properties = PropertyService.search(
                db, bot.id, listing_type=ListingType.SALE.value, limit=3
            )
            return cls._result(
                "Let me show you a few options to react to.\n\n"
                + PropertyService.describe_shortlist(properties, "buying"),
                state,
                properties=properties,
            )

        reply = cls._acknowledge(updates, lang) + cls._question_for(next_slot, state)
        return cls._result(reply, state)

    # ── Intent & slots ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_intent(message: str, state: Dict[str, Any]) -> str:
        """
        Intent for the property flow.

        Deliberately not the generic keyword counter: that scores "bhk" and "available" as
        buying signals, so "2 BHK on rent" and "just looking at what's available" both came out
        as buying. Explicit verbs win here, and browsing phrasing is checked on its own.
        """
        text = _normalise_localised(message)

        # Explicit handoff only. The generic detector counts "call me"/"callback" as handoff,
        # but in this flow those are the natural way to accept the advisor offer and should
        # start lead capture instead of ending the conversation.
        handoff_phrases = (
            "human", "real person", "advisor", "representative", "speak to someone",
            "talk to someone", "talk to a person", "agent", "contact support",
        )
        if any(phrase in text for phrase in handoff_phrases):
            return "human_assistance"
        rent_hit = next(
            (text.index(w) for w in ("rent", "lease", "tenant") if w in text), None
        )
        buy_hit = next(
            (text.index(w) for w in ("buy", "purchase", "invest") if w in text), None
        )

        if rent_hit is not None and buy_hit is not None:
            return "renting" if rent_hit < buy_hit else "buying"
        if rent_hit is not None:
            return "renting"
        if buy_hit is not None:
            return "buying"

        browsing_phrases = (
            "just looking", "browsing", "explore", "what's available", "whats available",
            "what is available", "show me options", "show me what", "no particular",
            "give me what", "list what", "anything available",
        )
        if any(phrase in text for phrase in browsing_phrases):
            return "browsing"
        # "show me what you have", "any 3 bhk available?" — a request to see inventory rather
        # than a fact question. Requires an inventory word, so "is parking available?" is not
        # hijacked.
        if re.search(r"\b(available|options|listings|inventory)\b", text) and re.search(
            r"\b(show|give|list|see|any|what)\b", text
        ):
            return "browsing"

        # Only carry forward a real intent. conversation_service pre-seeds state["intent"]
        # from the generic detector, which labels "call me" as human_assistance; inheriting
        # that would turn every callback request into a handoff.
        if state.get("intent") in {"buying", "renting", "browsing"}:
            return state["intent"]
        return "browsing"

    @staticmethod
    def _states_intent(message: str) -> bool:
        """True when the message itself says what the user wants (buy / rent / browse)."""
        text = _normalise_localised(message)
        markers = (
            "buy", "rent", "lease", "purchase", "invest", "just looking", "browsing",
            "explore", "what's available", "whats available", "what is available", "show me",
            "give me", "list what", "anything available",
        )
        return any(marker in text for marker in markers)

    @staticmethod
    def _has_requirements(state: Dict[str, Any]) -> bool:
        return any(state.get(key) for key in ("location", "bhk", "property_type", "budget_max"))

    @staticmethod
    def _ready_for_shortlist(state: Dict[str, Any]) -> bool:
        specific = sum(
            1 for key in ("location", "bhk", "property_type", "budget_max") if state.get(key)
        )
        return specific >= 2

    @staticmethod
    def _is_question(message: str) -> bool:
        text = message.strip().lower()
        if text.endswith("?"):
            return True
        starters = ("what", "how", "when", "where", "why", "who", "which", "does", "do you",
                    "is there", "can you", "tell me about")
        return text.startswith(starters)

    @staticmethod
    def _is_affirmative(message: str) -> bool:
        text = message.strip().lower()
        return text in AFFIRMATIVE or any(
            text.startswith(word) for word in ("yes", "yeah", "sure", "ok", "please")
        ) or "call me" in text or "contact me" in text

    @staticmethod
    def _wants_detail(message: str) -> bool:
        """Explicit request for property detail rather than a callback."""
        text = _normalise_localised(message)
        return any(
            phrase in text
            for phrase in ("tell me more", "more about", "details", "brochure", "explain")
        )

    @staticmethod
    def _is_negative(message: str) -> bool:
        text = message.strip().lower()
        return text in NEGATIVE or text.startswith(("no ", "not "))

    # ── Questions ─────────────────────────────────────────────────────────────

    # Question text lives in the catalogue; the flow only decides which slot to ask for.
    SLOT_MESSAGE_KEYS = {
        "location": "ask_location",
        "property_type": "ask_type",
        "bhk": "ask_bhk",
        "budget_max": "ask_budget",
        "amenities": "ask_amenities",
        "timeline": "ask_timeline",
        "purpose": "ask_purpose",
    }

    @classmethod
    def _slot_order(cls, state: Dict[str, Any]) -> List[str]:
        order = ["location", "property_type", "bhk", "purpose", "budget_max", "amenities", "timeline"]
        return order

    @classmethod
    def _next_slot(cls, state: Dict[str, Any]) -> Optional[str]:
        for slot in cls._slot_order(state):
            if state.get(slot):
                continue
            if slot in (state.get("asked") or []):
                continue
            return slot
        return None

    @classmethod
    def _question_for(cls, slot: str, state: Dict[str, Any]) -> str:
        state.setdefault("asked", []).append(slot)
        lang = state.get("language") or "en"
        if slot == "budget_max" and state.get("intent") == "renting":
            return translate(lang, "ask_budget_rent")
        key = cls.SLOT_MESSAGE_KEYS.get(slot)
        if not key:
            return translate(lang, "ask_location")
        return translate(lang, key)

    @classmethod
    def _pending_question(cls, state: Dict[str, Any]) -> str:
        slot = cls._next_slot(state)
        return cls._question_for(slot, state) if slot else ""

    @staticmethod
    def _acknowledge(updates: Dict[str, Any], language: str = "en") -> str:
        if not updates:
            return ""
        bits = []
        if updates.get("bhk"):
            bits.append(f"{updates['bhk']} BHK")
        if updates.get("property_type"):
            bits.append(updates["property_type"].lower())
        if updates.get("location"):
            bits.append(updates["location"])
        if updates.get("budget_max"):
            bits.append(str(updates["budget_max"]))
        if not bits:
            return ""
        return translate(language, "ack", details=", ".join(bits))

    # ── Shortlist helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _last_shortlist(state: Dict[str, Any]) -> List[Dict[str, Any]]:
        return state.get("last_shortlist_full") or []

    @classmethod
    def _describe_selected_property(
        cls, message: str, state: Dict[str, Any], language: str = "en"
    ) -> Optional[str]:
        shortlist = state.get("last_shortlist_full") or []
        if not shortlist:
            return None
        text = _normalise_localised(message)
        index = None
        ordinals = {"first": 0, "second": 1, "third": 2, "1st": 0, "2nd": 1, "3rd": 2}
        for word, position in ordinals.items():
            if word in text:
                index = position
                break
        if index is None:
            for position, prop in enumerate(shortlist):
                # Match on the project name ("Orion") rather than a fixed word position.
                for token in re.findall(r"[a-z]{4,}", prop["title"].lower()):
                    if token in text and token not in {"prycoons", "heights", "residency"}:
                        index = position
                        break
                if index is not None:
                    break
        if index is None and re.search(r"\b(tell me more|details|brochure)\b", text):
            index = 0
        if index is None or index >= len(shortlist):
            return None
        return cls._property_sentence(shortlist[index], language)

    @staticmethod
    def _property_sentence(prop: Dict[str, Any], language: str = "en") -> str:
        parts = [f"{prop['title']} — {prop['location']}, {prop['price_display']}."]
        if prop.get("description"):
            parts.append(prop["description"])
        if prop.get("amenities"):
            label = translate(language, "amenities_label")
            parts.append(f"{label}: " + ", ".join(prop["amenities"]) + ".")
        if prop.get("is_mock"):
            parts.append(translate(language, "detail_mock"))
        return " ".join(parts)

    @staticmethod
    def _lookup_property(db: Session, bot_id: int, message: str) -> Optional[Dict[str, Any]]:
        """Find exactly one catalogue property named or located in the message."""
        from app.models.property import Property

        text = _normalise_localised(message)
        generic = {
            "prycoons", "residency", "heights", "greens", "skyline", "central", "enclave",
            "villa", "apartment", "rental", "bhk", "flat", "plot",
        }
        matches: Dict[int, Property] = {}
        for row in db.query(Property).filter(Property.bot_id == bot_id).all():
            haystack = f"{row.title} {row.project_name or ''}".lower()
            tokens = set(re.findall(r"[a-z]{4,}", haystack)) - generic
            if any(token in text for token in tokens) or (row.location or "").lower() in text:
                matches[row.id] = row
        if len(matches) == 1:
            return PropertyService.to_dict(next(iter(matches.values())))
        return None

    # ── Lead capture ──────────────────────────────────────────────────────────

    @classmethod
    def _capture_lead_field(
        cls,
        db: Session,
        bot: Bot,
        conversation: Conversation,
        message: str,
        state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        field = state.get("lead_pending")
        text = message.strip()
        lang = state.get("language") or "en"

        if field == "lead_name":
            if cls._is_affirmative(text) or len(text) < 2:
                return cls._result(translate(lang, "lead_start"), state)
            state["lead_name"] = text[:120]
            state["lead_pending"] = "lead_phone"
            return cls._result(
                translate(lang, "lead_ask_phone", name=state["lead_name"]), state
            )

        if field == "lead_phone":
            digits = _numbers_only(text)
            if len(re.sub(r"\D", "", digits)) < 10:
                return cls._result(translate(lang, "lead_phone_invalid"), state)
            state["lead_phone"] = digits
            state["lead_pending"] = "lead_email"
            return cls._result(translate(lang, "lead_ask_email"), state)

        if field == "lead_email":
            lowered = text.lower()
            if lowered in {"skip", "no", "none", "not now", "छोड़ें", "છોડો"}:
                state["lead_email"] = None
            elif re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", lowered):
                state["lead_email"] = lowered
            else:
                return cls._result(translate(lang, "lead_email_invalid"), state)
            state["lead_pending"] = "lead_contact"
            return cls._result(translate(lang, "lead_ask_contact"), state)

        if field == "lead_contact":
            lowered = text.lower()
            chosen = next((label for key, label in CONTACT_CHOICES.items() if key in lowered), None)
            state["lead_contact"] = chosen or "Phone"
            state["lead_pending"] = None
            lead = cls._save_lead(db, bot, conversation, state)
            state["stage"] = STAGE_CONFIRM
            state["lead_id"] = lead.id if lead else None
            reply = translate(
                lang,
                "lead_done",
                name=state.get("lead_name"),
                contact=state["lead_contact"],
                phone=state.get("lead_phone"),
            )
            if state.get("lead_email"):
                reply += translate(lang, "lead_done_email", email=state["lead_email"])
            reply += "\n\n" + translate(lang, "lead_done_end")
            return cls._result(reply, state, lead=cls._lead_payload(state))

        return None

    @classmethod
    def _save_lead(
        cls, db: Session, bot: Bot, conversation: Conversation, state: Dict[str, Any]
    ) -> Optional[Lead]:
        requirements = cls._requirements_summary(state)
        lead = Lead(
            bot_id=bot.id,
            conversation_id=conversation.id if conversation else None,
            name=state.get("lead_name") or "Unknown",
            phone=state.get("lead_phone") or "",
            email=state.get("lead_email"),
            preferred_contact=state.get("lead_contact") or "Phone",
            requirements=requirements,
            intent=state.get("intent"),
            location=state.get("location"),
            budget_max=state.get("budget_max"),
        )
        db.add(lead)
        db.flush()
        from app.models.activity import ActivityType
        from app.services.activity_service import log_activity

        log_activity(
            db, ActivityType.LEAD_CAPTURED.value,
            user_id=getattr(bot.project, "user_id", None),
            entity_type="lead", entity_id=lead.id,
            metadata={"bot_id": bot.id, "intent": lead.intent},
        )
        db.commit()
        db.refresh(lead)
        logger.info(f"Lead {lead.id} captured for bot {bot.id} ({lead.intent})")
        return lead

    @staticmethod
    def _requirements_summary(state: Dict[str, Any]) -> str:
        bits = []
        if state.get("intent"):
            bits.append(state["intent"])
        if state.get("bhk"):
            bits.append(f"{state['bhk']} BHK")
        if state.get("property_type"):
            bits.append(state["property_type"])
        if state.get("location"):
            bits.append(f"in {state['location']}")
        if state.get("budget_max"):
            bits.append(f"budget up to {state['budget_max']}")
        if state.get("amenities"):
            bits.append("wants " + ", ".join(state["amenities"]))
        if state.get("timeline"):
            bits.append(f"timeline {state['timeline']}")
        return ", ".join(bits) or "No specific requirements captured"

    @staticmethod
    def _lead_payload(state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": state.get("lead_id"),
            "name": state.get("lead_name"),
            "phone": state.get("lead_phone"),
            "email": state.get("lead_email"),
            "preferred_contact": state.get("lead_contact"),
            "requirements": RealEstateFlow._requirements_summary(state),
        }

    # ── Result assembly ───────────────────────────────────────────────────────

    @staticmethod
    def _result(
        reply: str,
        state: Dict[str, Any],
        properties: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        lead: Optional[Dict[str, Any]] = None,
        handoff: bool = False,
    ) -> Dict[str, Any]:
        if properties:
            state["last_shortlist_full"] = properties
        return {
            "reply": reply,
            "state": state,
            "stage": state.get("stage"),
            "properties": properties or [],
            "citations": citations or [],
            "lead": lead,
            "handoff": handoff,
        }
