"""
ConversationService â€” handles:
  â€¢ Conversation creation / retrieval
  â€¢ Intent detection (structured rule + keyword hybrid)
  â€¢ Conversation state extraction and persistence
  â€¢ Full response pipeline: state â†’ intent â†’ RAG â†’ LLM â†’ save
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.bot import Bot
from app.models.project import Project
from app.models.conversation import Conversation, Message, ConversationStatus, MessageSender
from app.services.retrieval_service import RetrievalService
from app.services.llm_service import GROUNDED_REFUSAL_MESSAGE, LLMService
from app.services.real_estate_flow import RealEstateFlow
from app.services.language_service import LanguageService
from app.services.greeting_service import GreetingService
from app.core.messages import is_refusal
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Intent Detection
# ------------------------------------------------------------------------------

INTENT_SIGNALS: Dict[str, List[str]] = {
    "buying": [
        "buy", "purchase", "invest", "property", "flat", "apartment", "bhk",
        "price", "cost", "how much", "budget", "loan", "emi", "down payment",
        "booking", "available", "square feet", "sq ft", "possession", "registry",
        "token", "deposit"
    ],
    "renting": [
        "rent", "lease", "rental", "monthly", "pg", "paying guest", "furnish",
        "tenant", "landlord", "sublease", "accommodation", "room", "sharing"
    ],
    "general_question": [
        "what", "how", "when", "where", "why", "which", "who", "tell me",
        "explain", "describe", "info", "information", "details", "about"
    ],
    "human_assistance": [
        "human", "agent", "person", "advisor", "representative", "speak",
        "talk", "call", "connect", "real person", "support", "help me",
        "callback", "phone", "whatsapp", "contact"
    ],
}

HANDOFF_PHRASES = [
    "speak to a human", "talk to a person", "connect me to agent",
    "real person", "human advisor", "call me", "callback please",
    "i need help", "contact support", "whatsapp", "phone number"
]


def detect_intent(message: str, current_intent: Optional[str] = None) -> str:
    """
    Detect user intent from message text using structured signal matching.
    Returns the most likely intent string.
    Once an intent like 'buying' or 'renting' is set, it persists unless overridden.
    """
    msg_lower = message.lower()

    # Handoff check first (highest priority)
    if any(phrase in msg_lower for phrase in HANDOFF_PHRASES):
        return "human_assistance"

    scores: Dict[str, int] = {intent: 0 for intent in INTENT_SIGNALS}

    for intent, signals in INTENT_SIGNALS.items():
        for signal in signals:
            if signal in msg_lower:
                scores[intent] += 1

    best_intent = max(scores, key=lambda k: scores[k])
    best_score = scores[best_intent]

    # If no clear signal found, keep the current intent or default to browsing
    if best_score == 0:
        return current_intent or "browsing"

    # Sticky: once a strong commercial intent is set, only override with higher-priority one
    sticky_intents = {"buying", "renting"}
    if current_intent in sticky_intents and best_intent == "general_question":
        return current_intent

    return best_intent


# ------------------------------------------------------------------------------
# State Extraction
# ------------------------------------------------------------------------------

def extract_state_updates(message: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a user message for structured facts (location, BHK, budget, etc.)
    and merge them into the conversation state. Never removes existing values.
    """
    msg_lower = message.lower()
    updates: Dict[str, Any] = {}

    # BHK detection
    for bhk in ["1", "2", "3", "4", "5"]:
        if f"{bhk} bhk" in msg_lower or f"{bhk}bhk" in msg_lower:
            updates["bhk"] = int(bhk)
            break

    # Budget extraction (handles "1 crore", "50 lakhs", "80L", "â‚¹80 lakh")
    import re
    crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:cr(?:ore)?s?)", msg_lower)
    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:l(?:akh)?s?|lac)", msg_lower)
    if crore_match:
        updates["budget_max"] = int(float(crore_match.group(1)) * 10_000_000)
    elif lakh_match:
        updates["budget_max"] = int(float(lakh_match.group(1)) * 100_000)

    # Amenity extraction
    amenities_vocab = [
        "pool", "gym", "parking", "garden", "terrace", "balcony",
        "clubhouse", "security", "lift", "elevator", "generator",
        "cctv", "playground", "school", "hospital nearby", "metro"
    ]
    found_amenities = [a for a in amenities_vocab if a in msg_lower]
    if found_amenities:
        existing = current_state.get("amenities", [])
        combined = list(set(existing + found_amenities))
        updates["amenities"] = combined

    # Simple location extraction â€” look for "in <word>" or "at <word>" pattern
    location_match = re.search(r"\b(?:in|at|near|around|from)\s+([A-Za-z][A-Za-z\s]{2,20})\b", message)
    if location_match:
        location = location_match.group(1).strip()
        noise = {
            "the", "our", "your", "this", "that", "with", "bhk", "flat", "any", "all",
            "what", "what's", "which", "where", "how", "when", "who", "something", "area",
            "good", "nice", "budget", "same", "nearby", "available",
        }
        # A location has to look like a proper noun: "in Ambli" yes, "at what's available" no.
        if location[:1].isupper() and location.split()[0].lower() not in noise:
            updates["location"] = location.title()

    return updates


# ------------------------------------------------------------------------------
# ConversationService
# ------------------------------------------------------------------------------

class ConversationService:

    @staticmethod
    def _verify_bot(db: Session, bot_id: int, user_id: Optional[int] = None) -> Bot:
        """Get bot, optionally verifying ownership."""
        if user_id:
            bot = (
                db.query(Bot)
                .join(Project)
                .filter(Bot.id == bot_id, Project.user_id == user_id)
                .first()
            )
        else:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()

        if not bot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found.")
        return bot

    @staticmethod
    def create_conversation(
        db: Session,
        bot_id: int,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        context: Optional[Any] = None,
    ) -> Conversation:
        """
        Create a new conversation session.

        ``context`` optionally carries language/city/time hints used to build the opening
        greeting. Only coarse values (city, region, hour) are stored â€” never coordinates.
        """
        bot = ConversationService._verify_bot(db, bot_id, user_id)

        if not session_id:
            # The UI calls this whenever a chat opens. Reusing an existing empty active
            # conversation stops a page refresh from littering the history with blank
            # conversations that the user never sent a message in.
            reusable = (
                db.query(Conversation)
                .outerjoin(Message, Message.conversation_id == Conversation.id)
                .filter(
                    Conversation.bot_id == bot_id,
                    Conversation.status == ConversationStatus.ACTIVE.value,
                )
                .group_by(Conversation.id)
                .having(func.count(Message.id) == 0)
                .order_by(Conversation.id.desc())
                .first()
            )
            if reusable:
                # A conversation opened before greetings existed (or interrupted before the
                # greeting was written) is empty. Give it the opener now instead of returning
                # a blank transcript.
                already_has_messages = (
                    db.query(Message)
                    .filter(Message.conversation_id == reusable.id)
                    .first()
                )
                if not already_has_messages:
                    ConversationService._add_greeting(db, reusable, bot, context)
                return reusable
            session_id = uuid.uuid4().hex

        convo = Conversation(
            bot_id=bot_id,
            session_id=session_id,
            intent="browsing",
            status=ConversationStatus.ACTIVE.value,
            conversation_state="{}",
        )
        db.add(convo)
        db.flush()

        from app.models.activity import ActivityType
        from app.services.activity_service import log_activity

        log_activity(
            db, ActivityType.CONVERSATION_STARTED.value,
            user_id=user_id, entity_type="conversation", entity_id=convo.id,
            metadata={"bot_id": bot.id},
        )
        db.commit()
        db.refresh(convo)

        ConversationService._add_greeting(db, convo, bot, context)
        return convo

    @staticmethod
    def _add_greeting(db: Session, convo: Conversation, bot: Bot, context: Optional[Any]) -> None:
        """Store the contextual greeting as the conversation's first assistant message."""
        if not context:
            return
        state = json.loads(convo.conversation_state or "{}")
        language = (
            LanguageService.normalise(getattr(context, "language", None))
            or LanguageService.normalise(getattr(context, "language_hint", None))
            or state.get("language")
            or "en"
        )
        greeting = GreetingService.build(
            bot_name=bot.name,
            industry=getattr(getattr(bot, "project", None), "industry", None),
            language=language,
            city=getattr(context, "city", None),
            region=getattr(context, "region", None),
            local_hour=getattr(context, "local_hour", None),
            utc_offset_minutes=getattr(context, "utc_offset_minutes", None),
            language_hint=getattr(context, "language_hint", None),
            seed=f"conversation-{convo.id}",
            welcome=bot.welcome_message,
        )
        state.update({
            # The opener is already on screen; the flow starts in discovery rather than
            # greeting, so "Hi" does not trigger the greeting branch again.
            "stage": "discover",
            "language": language,
            "city": getattr(context, "city", None),
            "region": getattr(context, "region", None),
            "time_of_day": greeting["context"]["time_of_day"],
            "location_granted": bool(getattr(context, "location_granted", False)),
            "greeting_decision": greeting["decision"],
        })
        convo.conversation_state = json.dumps(state)
        db.add(
            Message(
                conversation_id=convo.id,
                sender=MessageSender.ASSISTANT.value,
                content=greeting["text"],
                metadata_json=json.dumps({
                    "type": "greeting",
                    "language": language,
                    "context": greeting["context"],
                }),
            )
        )
        db.commit()

    @staticmethod
    def get_conversation(
        db: Session,
        conversation_id: int,
        user_id: Optional[int] = None,
    ) -> Conversation:
        """Retrieve a conversation by ID with optional ownership check."""
        query = db.query(Conversation).filter(Conversation.id == conversation_id)
        convo = query.first()

        if not convo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        if user_id:
            # Verify ownership through bot â†’ project â†’ user
            bot = (
                db.query(Bot)
                .join(Project)
                .filter(Bot.id == convo.bot_id, Project.user_id == user_id)
                .first()
            )
            if not bot:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        return convo

    @staticmethod
    def list_conversations(
        db: Session,
        user_id: int,
        bot_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Conversation]:
        """List conversations for a bot or across all bots belonging to the user."""
        if bot_id:
            ConversationService._verify_bot(db, bot_id, user_id)
            return (
                db.query(Conversation)
                .filter(Conversation.bot_id == bot_id)
                .order_by(Conversation.started_at.desc())
                .limit(limit)
                .all()
            )
        return (
            db.query(Conversation)
            .join(Bot, Conversation.bot_id == Bot.id)
            .join(Project, Bot.project_id == Project.id)
            .filter(Project.user_id == user_id)
            .order_by(Conversation.started_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def send_message(
        db: Session,
        conversation_id: int,
        user_message: str,
        user_id: Optional[int] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full response pipeline:
          1. Load conversation + state
          2. Save user message
          3. Detect intent
          4. Extract & merge state
          5. RAG retrieval
          6. LLM generation
          7. Save assistant message
          8. Update conversation
          9. Return structured response
        """
        convo = ConversationService.get_conversation(db, conversation_id, user_id)

        # Block messaging on ended/handed-off conversations
        if convo.status in [ConversationStatus.ENDED.value, ConversationStatus.HANDED_OFF.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This conversation is {convo.status.lower()}. Please start a new one."
            )

        # Load state
        try:
            state = json.loads(convo.conversation_state or "{}")
        except (json.JSONDecodeError, TypeError):
            state = {}

        bot = db.query(Bot).filter(Bot.id == convo.bot_id).first()

        # -- Step 1: Save user message -----------------------------------------
        user_msg = Message(
            conversation_id=conversation_id,
            sender=MessageSender.USER.value,
            content=user_message,
            metadata_json=json.dumps({"raw": user_message}),
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # -- Step 2: Intent Detection ------------------------------------------
        new_intent = detect_intent(user_message, convo.intent)

        # -- Step 3: State Extraction & Merge ---------------------------------
        state_updates = extract_state_updates(user_message, state)
        state.update(state_updates)
        state["intent"] = new_intent

        # Language is part of the conversation, not a per-message setting: an explicit switch
        # wins, otherwise a clearly different language in the message switches the thread.
        # Switching language never touches the slots or the stage.
        state["language"] = LanguageService.resolve(
            language, user_message, current=state.get("language")
        )

        # -- Step 4: Build conversation history (needed by both paths) ---------
        recent_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc())
            .limit(10)
            .all()
        )
        recent_messages.reverse()

        history_for_llm = [
            ChatMessage(
                role="user" if m.sender == MessageSender.USER.value else "assistant",
                content=m.content,
            )
            for m in recent_messages[:-1]  # exclude the just-saved user message
        ]

        properties: List[Dict[str, Any]] = []
        lead_payload = None
        llm_prompt = None
        stage = None
        is_handoff = new_intent == "human_assistance"

        project = db.query(Project).filter(Project.id == bot.project_id).first()
        is_real_estate = bool(project and (project.industry or "").strip().lower() == "real estate")

        if is_real_estate and RealEstateFlow.should_handle(user_message, state):
            # -- Step 5a: Industry workflow (requirements â†’ shortlist â†’ lead) --
            def answer_knowledge(question: str):
                chunks = RetrievalService.search_relevant_chunks(
                    db=db, bot_id=bot.id, query=question, top_k=8
                )
                text = LLMService.generate_grounded_response(
                    bot=bot,
                    retrieved_chunks=chunks,
                    user_query=question,
                    conversation_history=history_for_llm,
                    conversation_state=state,
                )
                refused = is_refusal(text)
                cites = (
                    []
                    if refused or not chunks
                    else [
                        c.model_dump()
                        for c in RetrievalService.format_citations(
                            RetrievalService.display_citations(chunks)
                        )
                    ]
                )
                # Report the retrieval confidence for knowledge answers given inside the flow,
                # not just on the generic path.
                answer_knowledge.confidence = (
                    round(chunks[0][1], 4) if (chunks and not refused) else 0.0
                )
                return text, cites

            flow = RealEstateFlow.handle(
                db=db,
                bot=bot,
                conversation=convo,
                message=user_message,
                state=state,
                knowledge_answer=answer_knowledge,
            )
            reply = flow["reply"]
            state = flow["state"]
            # The flow owns intent for real-estate bots; the generic keyword counter scores
            # "bhk"/"available" as buying and would mislabel rentals and browsing.
            new_intent = state.get("intent") or new_intent
            stage = flow.get("stage")
            properties = flow.get("properties") or []
            citations_dicts = flow.get("citations") or []
            lead_payload = flow.get("lead")
            is_handoff = bool(flow.get("handoff"))
            confidence = float(getattr(answer_knowledge, "confidence", 0.0) or 0.0)
            if is_handoff:
                convo.status = ConversationStatus.HANDOFF_REQUESTED.value
        else:
            # -- Step 5b: Generic RAG path -------------------------------------
            if is_handoff:
                convo.status = ConversationStatus.HANDOFF_REQUESTED.value

            retrieved_chunks = RetrievalService.search_relevant_chunks(
                db=db, bot_id=bot.id, query=user_message, top_k=8
            )

            if is_handoff:
                reply = (
                    "Of course! ðŸ¤ I'm connecting you with a human advisor right now. "
                    "Someone from our team will be with you shortly. "
                    "You can also reach us directly at the contact details on our website."
                )
            else:
                reply = LLMService.generate_grounded_response(
                    bot=bot,
                    retrieved_chunks=retrieved_chunks,
                    user_query=user_message,
                    conversation_history=history_for_llm,
                    conversation_state=state,
                )

            # A refusal must never carry sources: showing a citation next to "I don't know" tells
            # the user the answer was grounded when it was not.
            refused = is_refusal(reply)
            if refused or is_handoff:
                citations_dicts = []
                confidence = 0.0
            else:
                citations = RetrievalService.format_citations(
                    RetrievalService.display_citations(retrieved_chunks)
                )
                citations_dicts = [c.model_dump() for c in citations]
                confidence = round(retrieved_chunks[0][1], 4) if retrieved_chunks else 0.0
                # No server LLM: hand the grounded prompt to the browser Puter client, if the
                # frontend has it enabled. It persists its polished answer back via PATCH.
                if retrieved_chunks and not LLMService.is_available():
                    llm_prompt = LLMService.build_puter_prompt(
                        bot, retrieved_chunks, user_message, state
                    )

        # -- Step 9: Save assistant message -----------------------------------
        reply = LLMService.normalise_refusal(LLMService.strip_markdown(reply))
        assistant_msg = Message(
            conversation_id=conversation_id,
            sender=MessageSender.ASSISTANT.value,
            content=reply,
            metadata_json=json.dumps({
                "intent": new_intent,
                "sources": citations_dicts,
                "confidence": confidence,
                "is_handoff": is_handoff,
                "state_snapshot": state,
                "stage": stage,
                "properties": properties,
                "lead": lead_payload,
            }),
        )
        db.add(assistant_msg)

        # -- Step 10: Persist conversation state -------------------------------
        convo.intent = new_intent
        convo.conversation_state = json.dumps(state)

        db.commit()
        db.refresh(assistant_msg)

        return {
            "conversation_id": conversation_id,
            "message_id": assistant_msg.id,
            "reply": reply,
            "intent": new_intent,
            "status": convo.status,
            "conversation_state": state,
            "sources": citations_dicts,
            "confidence": confidence,
            "is_handoff": is_handoff,
            "stage": stage,
            "properties": properties,
            "lead": lead_payload,
            "llm_prompt": llm_prompt,
            "language": state.get("language"),
        }

    @staticmethod
    def end_conversation(db: Session, conversation_id: int, user_id: Optional[int] = None) -> Conversation:
        """Mark a conversation as ended."""
        convo = ConversationService.get_conversation(db, conversation_id, user_id)
        convo.status = ConversationStatus.ENDED.value
        convo.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(convo)
        return convo
