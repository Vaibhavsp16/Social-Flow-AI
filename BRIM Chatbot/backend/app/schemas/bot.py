from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.project import ProjectResponse
from app.core.constants import PREDEFINED_INDUSTRIES

class BotBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    language: Optional[str] = "English"
    personality: Optional[str] = "Friendly & professional"
    welcome_message: Optional[str] = "Hi! How can I help you today?"
    status: Optional[str] = "Live"

class BotCreate(BotBase):
    project_id: int
    shareable_slug: Optional[str] = None

class BotUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    industry: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    personality: Optional[str] = None
    welcome_message: Optional[str] = None
    status: Optional[str] = None
    shareable_slug: Optional[str] = None

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PREDEFINED_INDUSTRIES:
            raise ValueError(f"Industry must be one of: {', '.join(PREDEFINED_INDUSTRIES)}")
        return v

class BotResponse(BotBase):
    id: int
    project_id: int
    shareable_slug: str
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectResponse] = None

    model_config = ConfigDict(from_attributes=True)
