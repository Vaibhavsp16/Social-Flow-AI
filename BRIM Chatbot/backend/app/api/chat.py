from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
from app.models.bot import Bot
from app.models.project import Project
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from app.api.auth import get_current_user
from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService

router = APIRouter(tags=["Chat & Grounded QA"])

@router.post("/bots/{bot_id}/chat", response_model=ChatQueryResponse)
def bot_chat_authenticated(
    bot_id: int,
    request: ChatQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a grounded semantic QA query against a specific bot's knowledge base.
    Requires authentication and project ownership verification.
    """
    bot = (
        db.query(Bot)
        .join(Project)
        .filter(Bot.id == bot_id, Project.user_id == current_user.id)
        .first()
    )
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you do not have permission to access it."
        )

    # 1. Semantic search strictly on this bot_id
    retrieved_chunks = RetrievalService.search_relevant_chunks(
        db=db,
        bot_id=bot.id,
        query=request.message,
        top_k=request.top_k or 4,
    )

    # 2. Generate grounded answer
    reply = LLMService.generate_grounded_response(
        bot=bot,
        retrieved_chunks=retrieved_chunks,
        user_query=request.message,
        conversation_history=request.conversation_history,
    )

    # 3. Format source citations
    citations = RetrievalService.format_citations(retrieved_chunks)

    return ChatQueryResponse(
        reply=reply,
        bot_id=bot.id,
        bot_name=bot.name,
        sources=citations,
        confidence=round(retrieved_chunks[0][1], 4) if retrieved_chunks else 0.0,
    )

@router.post("/public/bots/{slug}/chat", response_model=ChatQueryResponse)
def bot_chat_public(
    slug: str,
    request: ChatQueryRequest,
    db: Session = Depends(get_db),
):
    """
    Publicly accessible grounded chat endpoint for published bots.
    """
    bot = db.query(Bot).filter(Bot.shareable_slug == slug).first()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found."
        )

    # 1. Semantic search strictly on this bot_id
    retrieved_chunks = RetrievalService.search_relevant_chunks(
        db=db,
        bot_id=bot.id,
        query=request.message,
        top_k=request.top_k or 4,
    )

    # 2. Generate grounded answer
    reply = LLMService.generate_grounded_response(
        bot=bot,
        retrieved_chunks=retrieved_chunks,
        user_query=request.message,
        conversation_history=request.conversation_history,
    )

    # 3. Format source citations
    citations = RetrievalService.format_citations(retrieved_chunks)

    return ChatQueryResponse(
        reply=reply,
        bot_id=bot.id,
        bot_name=bot.name,
        sources=citations,
        confidence=round(retrieved_chunks[0][1], 4) if retrieved_chunks else 0.0,
    )
