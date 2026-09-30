from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ─── Message schemas ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender: str
    content: str
    timestamp: datetime
    metadata_json: Optional[str] = "{}"

    model_config = ConfigDict(from_attributes=True)


# ─── Conversation schemas ─────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    bot_id: int
    session_id: Optional[str] = None  # auto-generated if not provided


class ConversationResponse(BaseModel):
    id: int
    bot_id: int
    session_id: str
    intent: Optional[str] = "browsing"
    status: str
    conversation_state: Optional[str] = "{}"
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    id: int
    bot_id: int
    session_id: str
    intent: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ─── Chat send message ────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class SendMessageResponse(BaseModel):
    conversation_id: int
    message_id: int
    reply: str
    intent: str
    status: str
    conversation_state: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    confidence: float = 0.0
    is_handoff: bool = False
