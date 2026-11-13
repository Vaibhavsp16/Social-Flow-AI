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
    # Stable browser identity, so several chats by one person count as one visitor.
    visitor_id: Optional[str] = Field(default=None, max_length=64)
    # web | embed | preview
    channel: Optional[str] = None
    # Optional greeting context. City/region only — precise coordinates are never accepted.
    language: Optional[str] = None
    language_hint: Optional[str] = None  # navigator.language / Accept-Language
    city: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = Field(default=None, max_length=64)
    local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    utc_offset_minutes: Optional[int] = Field(default=None, ge=-720, le=840)
    location_granted: bool = False


class ConversationResponse(BaseModel):
    id: int
    bot_id: int
    session_id: str
    visitor_id: Optional[str] = None
    channel: Optional[str] = "web"
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
    visitor_id: Optional[str] = None
    channel: Optional[str] = "web"
    intent: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ─── Chat send message ────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    # Explicit language switch from the UI; omitted means "detect from the message".
    language: Optional[str] = None


class ContactSubmit(BaseModel):
    """The contact card the chat shows after an idle period or mid-conversation."""

    name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=255)
    # When the person is comfortable being called. Free text: "weekday evenings after 6".
    preferred_time: Optional[str] = Field(default=None, max_length=160)
    preferred_contact: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=2000)
    timezone: Optional[str] = Field(default=None, max_length=64)
    # idle | mid_conversation | form
    source: Optional[str] = "form"


class NudgeRequest(BaseModel):
    # idle | contact
    kind: str = "idle"


class PublicConversationCreate(BaseModel):
    visitor_id: Optional[str] = Field(default=None, max_length=64)
    channel: Optional[str] = Field(default=None, max_length=32)
    language: Optional[str] = None
    language_hint: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = Field(default=None, max_length=64)
    local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    utc_offset_minutes: Optional[int] = Field(default=None, ge=-720, le=840)
    location_granted: bool = False


class MessageContentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


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
    # Real-estate workflow output (null/empty for other industries).
    stage: Optional[str] = None
    properties: List[Dict[str, Any]] = []
    lead: Optional[Dict[str, Any]] = None
    # A meeting the bot arranged in this turn.
    meeting: Optional[Dict[str, Any]] = None
    # When set, the UI should render its contact form after this reply.
    contact_prompt: Optional[Dict[str, Any]] = None
    # Grounded prompt for the optional browser-side Puter client (null when a server LLM is set).
    llm_prompt: Optional[str] = None
    language: Optional[str] = None
