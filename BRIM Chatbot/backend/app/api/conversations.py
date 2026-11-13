from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.database.session import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ContactSubmit,
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    MessageContentUpdate,
    NudgeRequest,
    PublicConversationCreate,
    SendMessageRequest,
    SendMessageResponse,
)
from app.api.auth import get_current_user
from app.services import contact_service
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["Conversations"])


# ── Create a new conversation ─────────────────────────────────────────────────
@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new conversation session with a bot."""
    convo = ConversationService.create_conversation(
        db=db,
        bot_id=payload.bot_id,
        session_id=payload.session_id,
        context=payload,
        user_id=current_user.id,
        visitor_id=payload.visitor_id,
        channel=payload.channel or "preview",
    )
    return convo


# ── Public: create conversation by bot slug ───────────────────────────────────
@router.post("/public/conversations/{slug}", response_model=ConversationResponse, status_code=201)
def create_public_conversation(
    slug: str,
    payload: Optional[PublicConversationCreate] = None,
    db: Session = Depends(get_db),
):
    """Start a new public conversation with a bot by its shareable slug.

    The visitor id is what keeps one person's several chats attributable to one person; the body is
    optional so an existing embed that posts nothing still works.
    """
    from app.models.bot import Bot
    bot = db.query(Bot).filter(Bot.shareable_slug == slug).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")
    convo = ConversationService.create_conversation(
        db=db,
        bot_id=bot.id,
        visitor_id=getattr(payload, "visitor_id", None),
        channel=getattr(payload, "channel", None) or "web",
        context=payload,
    )
    return convo


# ── List conversations (all or by bot) ─────────────────────────────────────────
@router.get("/conversations", response_model=List[ConversationSummary])
def list_all_conversations(
    bot_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, le=200),
    visitor_id: Optional[str] = Query(
        default=None, description="Only this visitor's chats, for the in-chat sidebar"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List conversations for all bots or filtered by bot_id (newest first)."""
    convos = ConversationService.list_conversations(
        db=db, user_id=current_user.id, bot_id=bot_id, limit=limit, visitor_id=visitor_id
    )
    results = []
    for c in convos:
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        results.append(
            ConversationSummary(
                id=c.id,
                bot_id=c.bot_id,
                session_id=c.session_id,
                # These two are built by hand, so every field has to be listed explicitly. They were
                # missing, which made the API report visitor_id as null for rows that had one and
                # left the chat-history Visitor column permanently blank.
                visitor_id=c.visitor_id,
                channel=c.channel,
                intent=c.intent,
                status=c.status,
                started_at=c.started_at,
                ended_at=c.ended_at,
                message_count=msg_count,
            )
        )
    return results


@router.get("/bots/{bot_id}/conversations", response_model=List[ConversationSummary])
def list_conversations_for_bot(
    bot_id: int,
    limit: int = Query(default=50, le=200),
    visitor_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all conversations for a specific bot (newest first)."""
    return list_all_conversations(
        bot_id=bot_id, limit=limit, visitor_id=visitor_id, db=db, current_user=current_user
    )


# ── Get a single conversation with full message history ───────────────────────
@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a conversation with full message history."""
    return ConversationService.get_conversation(db, conversation_id, current_user.id)


# ── Public: get conversation ──────────────────────────────────────────────────
@router.get("/public/conversations/{conversation_id}", response_model=ConversationResponse)
def get_public_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve a public conversation by ID (no auth required)."""
    return ConversationService.get_conversation(db, conversation_id)


# ── Send a message ────────────────────────────────────────────────────────────
@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a user message and get an AI response.

    Full pipeline: state → intent detection → RAG → LLM → save → return.
    """
    result = ConversationService.send_message(
        db=db,
        conversation_id=conversation_id,
        user_message=payload.message,
        user_id=current_user.id,
        language=payload.language,
    )
    return SendMessageResponse(**result)


# ── Public: send message (no auth, e.g. embedded widget) ─────────────────────
@router.post("/public/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
def send_public_message(
    conversation_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
):
    """Send a message to a public bot conversation (no authentication required)."""
    result = ConversationService.send_message(
        db=db,
        conversation_id=conversation_id,
        user_message=payload.message,
        language=payload.language,
    )
    return SendMessageResponse(**result)


# ── Replace an assistant message (browser-side Puter answer) ──────────────────
@router.patch("/messages/{message_id}")
def update_message_content(
    message_id: int,
    payload: MessageContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Persist an assistant reply produced elsewhere (the optional Puter client) so the transcript
    shows what the visitor actually saw.
    """
    from app.models.bot import Bot
    from app.models.project import Project

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found.")
    convo = db.query(Conversation).filter(Conversation.id == message.conversation_id).first()
    owned = (
        db.query(Bot)
        .join(Project, Bot.project_id == Project.id)
        .filter(Bot.id == convo.bot_id, Project.user_id == current_user.id)
        .first()
        if convo
        else None
    )
    if not owned:
        raise HTTPException(status_code=403, detail="Access denied.")

    message.content = payload.content
    db.commit()
    db.refresh(message)
    return {"id": message.id, "content": message.content}


# ── Request a human advisor ───────────────────────────────────────────────────
@router.post("/conversations/{conversation_id}/handoff", response_model=ConversationResponse)
def request_handoff(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flag the conversation for a human advisor and leave an audit message in the transcript."""
    from app.models.conversation import ConversationStatus, MessageSender

    convo = ConversationService.get_conversation(db, conversation_id, current_user.id)
    convo.status = ConversationStatus.HANDOFF_REQUESTED.value
    db.add(
        Message(
            conversation_id=convo.id,
            sender=MessageSender.SYSTEM.value,
            content="A human advisor was requested from the chat.",
            metadata_json=json.dumps({"event": "handoff_requested"}),
        )
    )
    from app.models.activity import ActivityType
    from app.services.activity_service import log_activity

    log_activity(
        db, ActivityType.HANDOFF_REQUESTED.value,
        user_id=current_user.id, entity_type="conversation", entity_id=convo.id,
    )
    db.commit()
    db.refresh(convo)
    return convo


# ── End a conversation ────────────────────────────────────────────────────────
@router.patch("/conversations/{conversation_id}/end", response_model=ConversationResponse)
def end_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a conversation as ended."""
    return ConversationService.end_conversation(db, conversation_id, current_user.id)


# ── Proactive idle nudge ──────────────────────────────────────────────────────
@router.post("/public/conversations/{conversation_id}/nudge")
def nudge_public_conversation(
    conversation_id: int,
    payload: Optional[NudgeRequest] = None,
    db: Session = Depends(get_db),
):
    """Ask the bot to re-engage a visitor who went quiet.

    Only fires once per conversation and never when contact details are already on file. The
    frontend's idle timer calls this; a closed tab cannot hammer it because the second call returns
    ``sent: false``.
    """
    return ConversationService.nudge(
        db, conversation_id, kind=getattr(payload, "kind", "idle") or "idle"
    )


# ── Contact details submitted from the chat card ──────────────────────────────
def _store_contact(db: Session, conversation_id: int, payload: ContactSubmit, user_id=None):
    from app.models.bot import Bot

    convo = ConversationService.get_conversation(db, conversation_id, user_id)
    bot = db.query(Bot).filter(Bot.id == convo.bot_id).first()

    phone = contact_service.normalise_phone(payload.phone) if payload.phone else None
    email = contact_service.extract_email(payload.email) if payload.email else None
    if payload.phone and not phone:
        raise HTTPException(
            status_code=422,
            detail="That phone number doesn't look complete. Please include the area code or all 10 digits.",
        )
    if not phone and not email:
        raise HTTPException(status_code=422, detail="Add a phone number or an email address.")

    try:
        state = json.loads(convo.conversation_state or "{}")
    except (ValueError, TypeError):
        state = {}

    lead = contact_service.upsert_lead(
        db, bot, convo,
        name=(payload.name or "").strip() or None,
        phone=phone,
        email=email,
        preferred_contact=payload.preferred_contact,
        preferred_time=(payload.preferred_time or "").strip() or None,
        timezone=payload.timezone or state.get("timezone"),
        intent=state.get("intent"),
        location=state.get("location"),
        budget_max=state.get("budget_max"),
        notes=payload.notes,
        source=payload.source or "form",
    )

    from app.core.messages import translate

    language = state.get("language") or "en"
    company = bot.company_name or "the team"
    if lead.phone:
        text = translate(
            language, "contact_thanks",
            name=f" {lead.name}" if lead.name and lead.name != "Website visitor" else "",
            phone=lead.phone,
            time=(
                translate(language, "contact_time_hint", time=lead.preferred_time)
                if lead.preferred_time else ""
            ),
            company=company,
        )
    else:
        text = translate(language, "contact_ask", company=company)

    db.add(
        Message(
            conversation_id=convo.id,
            sender="ASSISTANT",
            content=text,
            metadata_json=json.dumps({"type": "contact_captured", "lead_id": lead.id}),
        )
    )
    state["contact_captured"] = True
    convo.conversation_state = json.dumps(state)
    db.commit()

    return {
        "saved": True,
        "lead": contact_service.lead_payload(lead),
        "reply": text,
        "message": text,
        "contact_prompted": True,
    }


@router.post("/public/conversations/{conversation_id}/contact")
def submit_contact_public(
    conversation_id: int,
    payload: ContactSubmit,
    db: Session = Depends(get_db),
):
    """Store the contact details a visitor typed into the chat's contact card."""
    return _store_contact(db, conversation_id, payload)


@router.post("/conversations/{conversation_id}/contact")
def submit_contact_authenticated(
    conversation_id: int,
    payload: ContactSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Same as the public endpoint, used by the owner's preview chat."""
    return _store_contact(db, conversation_id, payload, current_user.id)
