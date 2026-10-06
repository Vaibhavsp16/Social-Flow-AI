from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: user, assistant, or system")
    content: str = Field(..., description="Message text content")

    model_config = ConfigDict(from_attributes=True)

class ChatQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User question")
    conversation_history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Recent conversation history")
    top_k: Optional[int] = Field(default=4, ge=1, le=10)
    threshold: Optional[float] = Field(default=0.02, ge=0.0, le=1.0)

class SourceCitation(BaseModel):
    source_id: int
    source_name: str
    source_type: str
    source_url: Optional[str] = None
    page_number: Optional[str] = None
    chunk_index: int
    similarity_score: float
    snippet: str

    model_config = ConfigDict(from_attributes=True)

class ChatQueryResponse(BaseModel):
    reply: str
    sources: List[SourceCitation] = []
    grounded: bool = True
    bot_id: int
    bot_name: str
    confidence: Optional[float] = 1.0

    model_config = ConfigDict(from_attributes=True)
