from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.database.session import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    SendMessageRequest,
    SendMessageResponse,
)
from app.api.auth import get_current_user
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
        user_id=current_user.id,
    )
    return convo


# ── Public: create conversation by bot slug ───────────────────────────────────
@router.post("/public/conversations/{slug}", response_model=ConversationResponse, status_code=201)
def create_public_conversation(
    slug: str,
    db: Session = Depends(get_db),
):
    """Start a new public conversation with a bot by its shareable slug."""
    from app.models.bot import Bot
    bot = db.query(Bot).filter(Bot.shareable_slug == slug).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")
    convo = ConversationService.create_conversation(db=db, bot_id=bot.id)
    return convo


# ── List conversations (all or by bot) ─────────────────────────────────────────
@router.get("/conversations", response_model=List[ConversationSummary])
def list_all_conversations(
    bot_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List conversations for all bots or filtered by bot_id (newest first)."""
    convos = ConversationService.list_conversations(
        db=db, user_id=current_user.id, bot_id=bot_id, limit=limit
    )
    results = []
    for c in convos:
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        results.append(
            ConversationSummary(
                id=c.id,
                bot_id=c.bot_id,
                session_id=c.session_id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all conversations for a specific bot (newest first)."""
    return list_all_conversations(bot_id=bot_id, limit=limit, db=db, current_user=current_user)


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
    )
    return SendMessageResponse(**result)


# ── End a conversation ────────────────────────────────────────────────────────
@router.patch("/conversations/{conversation_id}/end", response_model=ConversationResponse)
def end_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a conversation as ended."""
    return ConversationService.end_conversation(db, conversation_id, current_user.id)
