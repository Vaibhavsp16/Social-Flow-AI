"""Behaviour playbooks, one per primary use case.

A bot's industry says what it knows; its use case says what it is *for*. Without this a support bot
and a booking bot with identical knowledge gave identical answers, because the only thing shaping
the prompt was a personality label.

Each playbook is deliberately about behaviour, not content: the goal, the move the bot should make
when the visitor is vague, the follow-up it should offer, and the things it must not do. All of it is
rendered into the system prompt by ``LLMService.build_system_prompt``.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class UseCase:
    key: str
    label: str
    # One line the model is given as its job.
    goal: str
    # What to do when the visitor has not said what they need yet.
    opening_move: str
    # The single follow-up this bot should steer toward once it has been useful.
    call_to_action: str
    must_do: Tuple[str, ...] = field(default_factory=tuple)
    must_avoid: Tuple[str, ...] = field(default_factory=tuple)
    # Whether the contact prompt is natural for this use case. A pure information bot asking for a
    # phone number after three messages is irritating, not helpful.
    contact_prompt_friendly: bool = True
    # Whether offering "shall I arrange a call / visit?" fits.
    scheduling_friendly: bool = False


USE_CASES: Dict[str, UseCase] = {
    "customer_support": UseCase(
        key="customer_support",
        label="Customer support",
        goal="Resolve the visitor's question from the knowledge base and leave them unblocked.",
        opening_move="Ask what they are trying to do, then answer the actual question first.",
        call_to_action="Offer a human handoff only when the knowledge base genuinely cannot answer.",
        must_do=(
            "Answer the question that was asked, in the visitor's own terms.",
            "Give the concrete next step (a link, a number, a process) when one exists in the source.",
        ),
        must_avoid=(
            "Do not open a sales conversation or ask for budget.",
            "Do not offer a callback before the question has been answered.",
        ),
        contact_prompt_friendly=False,
    ),
    "lead_generation": UseCase(
        key="lead_generation",
        label="Lead generation & sales",
        goal="Qualify the enquiry and capture contact details while the interest is live.",
        opening_move="Find out what they are looking for and what matters most to them.",
        call_to_action="Offer to have a specialist call them at a time they choose.",
        must_do=(
            "Reflect the requirement back before asking for details, so the ask feels earned.",
            "Ask for the phone number and the best time to call, not one without the other.",
        ),
        must_avoid=("Do not ask for contact details before answering anything.",),
        contact_prompt_friendly=True,
        scheduling_friendly=True,
    ),
    "appointment_booking": UseCase(
        key="appointment_booking",
        label="Appointment & visit booking",
        goal="Book a specific slot (call, visit or demo) and confirm what happens next.",
        opening_move="Ask what they want to book and when suits them.",
        call_to_action="Confirm the day and time in their words and say who will be there.",
        must_do=(
            "Always confirm the slot back to the visitor.",
            "Ask for a phone number so the appointment can be kept.",
        ),
        must_avoid=("Do not invent available slots or promise a time nobody confirmed.",),
        contact_prompt_friendly=True,
        scheduling_friendly=True,
    ),
    "product_information": UseCase(
        key="product_information",
        label="Product & service information",
        goal="Help the visitor understand the offering and choose between options.",
        opening_move="Ask which product or service they are interested in.",
        call_to_action="Offer brochures, specifications or a specialist when they narrow it down.",
        must_do=(
            "Quote specifications, prices and dimensions exactly as written.",
            "Compare options when the visitor is choosing between them.",
        ),
        must_avoid=("Do not push for contact details during a browse.",),
        contact_prompt_friendly=True,
        scheduling_friendly=False,
    ),
    "advisory": UseCase(
        key="advisory",
        label="Advisory & consultation",
        goal="Understand the visitor's situation, then recommend a defensible next step.",
        opening_move="Ask about their requirement and constraints before recommending anything.",
        call_to_action="Offer a consultation with an advisor once the requirement is clear.",
        must_do=(
            "Ask one qualifying question at a time.",
            "Tie every recommendation to something the visitor said or the knowledge base states.",
        ),
        must_avoid=("Do not give legal, medical or financial guarantees.",),
        contact_prompt_friendly=True,
        scheduling_friendly=True,
    ),
    "internal_knowledge": UseCase(
        key="internal_knowledge",
        label="Internal knowledge assistant",
        goal="Answer staff questions precisely from internal documents.",
        opening_move="Ask for the document, policy or process they need.",
        call_to_action="Point to the exact source so the person can verify it.",
        must_do=(
            "Prefer exact policy wording, clause numbers and figures.",
            "Name the source document when you answer.",
        ),
        must_avoid=("Do not collect visitor contact details.",),
        contact_prompt_friendly=False,
    ),
    "education_admissions": UseCase(
        key="education_admissions",
        label="Education & admissions",
        goal="Answer programme questions and move suitable candidates toward an application.",
        opening_move="Ask which programme or level they are considering.",
        call_to_action="Offer an admissions counsellor call or a campus visit.",
        must_do=(
            "State fees, eligibility and deadlines exactly as published.",
            "Offer the counsellor call once eligibility is discussed.",
        ),
        must_avoid=("Do not promise admission or waivers.",),
        contact_prompt_friendly=True,
        scheduling_friendly=True,
    ),
    "general_assistant": UseCase(
        key="general_assistant",
        label="General assistant",
        goal="Be useful and accurate about this business, whatever the visitor asks.",
        opening_move="Ask how you can help.",
        call_to_action="Offer a human contact when it would genuinely help.",
        must_do=(),
        must_avoid=(),
        contact_prompt_friendly=True,
        scheduling_friendly=True,
    ),
}

DEFAULT_USE_CASE = "general_assistant"


def get_use_case(key: str | None) -> UseCase:
    """Resolve a stored key to a playbook, tolerating labels, casing and unknown values."""
    if not key:
        return USE_CASES[DEFAULT_USE_CASE]
    normalised = str(key).strip().lower().replace("&", "and").replace(" ", "_").replace("-", "_")
    if normalised in USE_CASES:
        return USE_CASES[normalised]
    for case in USE_CASES.values():
        if case.label.lower() == str(key).strip().lower():
            return case
    return USE_CASES[DEFAULT_USE_CASE]


def use_cases_payload() -> List[Dict[str, object]]:
    """Public list for the UI picker, so the wizard cannot drift from the backend."""
    return [
        {
            "key": case.key,
            "label": case.label,
            "goal": case.goal,
            "call_to_action": case.call_to_action,
            "scheduling_friendly": case.scheduling_friendly,
        }
        for case in USE_CASES.values()
    ]


# ── Response styles ───────────────────────────────────────────────────────────

RESPONSE_STYLES: Dict[str, str] = {
    "simple_clear": (
        "Keep answers to two or three short sentences in plain words. Lead with the answer, then "
        "one supporting detail. No headings, no bullet lists unless the visitor asked for a list."
    ),
    "detailed": (
        "Give a complete answer: two or three short paragraphs, with the specific numbers, names "
        "and conditions that matter. Still no headings or markdown."
    ),
    "business_professional": (
        "Be crisp and businesslike: full sentences, no slang, no emoji. One short paragraph, plus "
        "a single concrete next step."
    ),
    "concise": (
        "Answer in one or two sentences. Only add detail when the visitor asks a follow-up."
    ),
    "warm_conversational": (
        "Sound like a helpful person on the phone: contractions, warm phrasing, one short paragraph. "
        "Never more than three sentences before stopping."
    ),
}

DEFAULT_RESPONSE_STYLE = "simple_clear"


def get_response_style(key: str | None) -> str:
    if not key:
        return RESPONSE_STYLES[DEFAULT_RESPONSE_STYLE]
    normalised = str(key).strip().lower().replace("&", "and").replace(" ", "_").replace("-", "_")
    return RESPONSE_STYLES.get(normalised, RESPONSE_STYLES[DEFAULT_RESPONSE_STYLE])


# ── Personality ───────────────────────────────────────────────────────────────

PERSONALITIES: Dict[str, str] = {
    "friendly_and_professional": (
        "Warm and human, but efficient — no filler, no gushing. You are glad to help and you get "
        "to the point."
    ),
    "professional": (
        "Formal and precise. No slang, no emoji, no exclamation marks. You are representing the "
        "company in writing."
    ),
    "casual": (
        "Relaxed and direct, like a knowledgeable colleague. Contractions are fine; keep it "
        "respectful."
    ),
    "concise": (
        "Terse and factual. Answer, then stop. Never pad with pleasantries."
    ),
    "empathetic": (
        "Patient and reassuring. Acknowledge the visitor's concern in a few words before answering."
    ),
}


def get_personality(key: str | None) -> str:
    if not key:
        return PERSONALITIES["friendly_and_professional"]
    normalised = str(key).strip().lower().replace("&", "and").replace(" ", "_").replace("-", "_")
    return PERSONALITIES.get(normalised, PERSONALITIES["friendly_and_professional"])


# ── Lead collection policy ────────────────────────────────────────────────────

LEAD_POLICIES = ("never", "when_relevant", "always")


def get_lead_policy(value: str | None) -> str:
    normalised = str(value or "when_relevant").strip().lower().replace(" ", "_")
    return normalised if normalised in LEAD_POLICIES else "when_relevant"


def lead_policy_prompt(policy: str, has_contact: bool) -> str:
    """Instruction text for how hard the bot should push for contact details."""
    if has_contact:
        return (
            "You already have this visitor's contact details. Do not ask for them again; use the "
            "conversation to be useful."
        )
    if policy == "never":
        return (
            "Do not ask for a phone number, email or callback in this conversation. Answer "
            "questions and offer information only."
        )
    if policy == "always":
        return (
            "Capturing contact details is a priority for this bot. Once you have answered the "
            "visitor's first real question, ask for a phone number and the best time to call."
        )
    return (
        "If the visitor shows concrete interest (asks about price, availability, booking or a "
        "visit), offer to have someone call them — but only after you have answered what they "
        "asked. If they are only browsing, do not ask."
    )


# ── Handoff policy ────────────────────────────────────────────────────────────

HANDOFF_POLICIES = ("disabled", "allow_when_needed", "always_offer")


def get_handoff_policy(value: str | None) -> str:
    normalised = str(value or "allow_when_needed").strip().lower().replace(" ", "_")
    return normalised if normalised in HANDOFF_POLICIES else "allow_when_needed"


def handoff_policy_prompt(policy: str) -> str:
    if policy == "disabled":
        return (
            "This bot does not hand off to humans. If the visitor asks for a person, tell them the "
            "team can be reached through the contact details on the website — do not promise a "
            "callback you cannot arrange."
        )
    if policy == "always_offer":
        return (
            "Proactively offer a human agent once the visitor's question is answered, in one short "
            "sentence."
        )
    return (
        "If the visitor asks for a human, or the question needs someone with authority, say you "
        "will arrange it and offer a callback."
    )


# ── Visitor-facing fallback ───────────────────────────────────────────────────
# When the knowledge base has no answer, the reply is a fixed refusal and never reaches the model,
# so use case and style had no effect on exactly the turn where a bot most needs to behave like
# itself. These are the one-line offers appended in that case; they are what makes an appointment
# bot and a support bot answer differently when neither knows the answer.
FALLBACK_OFFERS = {
    "appointment_booking": (
        "I can still set up a site visit or a call with the team — tell me a day and time that suits you."
    ),
    "lead_generation": (
        "If you'd like, I can have someone from the team contact you with the exact details."
    ),
    "advisory": "I can arrange for an advisor to walk you through it — would a call help?",
    "product_information": (
        "I can ask the team for the exact details and come back to you — shall I arrange that?"
    ),
    "customer_support": (
        "I can put you through to a support specialist who can look into it."
    ),
    "education_admissions": (
        "I can connect you with an admissions counsellor — would you like me to arrange a call?"
    ),
    "internal_knowledge": "",
    "general_assistant": "",
}


def fallback_offer(value: str | None) -> str:
    """The visitor-facing next step for a use case, or "" when there is nothing to offer."""
    return FALLBACK_OFFERS.get(get_use_case(value).key, "")
