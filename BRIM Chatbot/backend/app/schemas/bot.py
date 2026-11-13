from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.project import ProjectResponse
from app.core.constants import PREDEFINED_INDUSTRIES
from app.core.use_cases import LEAD_POLICIES, HANDOFF_POLICIES, USE_CASES

RESPONSE_STYLE_KEYS = (
    "simple_clear", "detailed", "business_professional", "concise", "warm_conversational",
)


def _normalise_choice(value: Optional[str], allowed: tuple, field: str) -> Optional[str]:
    if value is None:
        return None
    normalised = str(value).strip().lower().replace("&", "and").replace(" ", "_").replace("-", "_")
    if normalised not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return normalised


class BotBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    language: Optional[str] = "English"
    personality: Optional[str] = "Friendly & professional"
    welcome_message: Optional[str] = "Hi! How can I help you today?"
    status: Optional[str] = "Live"


class BotBehaviour(BaseModel):
    """The settings that change how the bot answers, as opposed to what it knows."""

    primary_use_case: Optional[str] = None
    response_style: Optional[str] = None
    lead_collection: Optional[str] = None
    human_handoff: Optional[str] = None
    contact_after_messages: Optional[int] = Field(default=None, ge=0, le=50)
    idle_prompt_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    company_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("primary_use_case")
    @classmethod
    def check_use_case(cls, v: Optional[str]) -> Optional[str]:
        return _normalise_choice(v, tuple(USE_CASES.keys()), "primary_use_case")

    @field_validator("response_style")
    @classmethod
    def check_style(cls, v: Optional[str]) -> Optional[str]:
        return _normalise_choice(v, RESPONSE_STYLE_KEYS, "response_style")

    @field_validator("lead_collection")
    @classmethod
    def check_lead_policy(cls, v: Optional[str]) -> Optional[str]:
        return _normalise_choice(v, LEAD_POLICIES, "lead_collection")

    @field_validator("human_handoff")
    @classmethod
    def check_handoff(cls, v: Optional[str]) -> Optional[str]:
        return _normalise_choice(v, HANDOFF_POLICIES, "human_handoff")


class BotCreate(BotBase, BotBehaviour):
    project_id: int
    shareable_slug: Optional[str] = None


class BotUpdate(BotBehaviour):
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


class BotResponse(BotBase, BotBehaviour):
    id: int
    project_id: int
    # What the chat actually opens with; `welcome_message` is the stored configuration.
    greeting_preview: Optional[str] = None
    shareable_slug: str
    custom_domain: Optional[str] = None
    domain_status: Optional[str] = "none"
    domain_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DomainUpdate(BaseModel):
    domain: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Hostname the company owns, e.g. chat.acme.com. Empty string clears it.",
    )


class DomainStatus(BaseModel):
    domain: Optional[str] = None
    status: str = "none"
    token: Optional[str] = None
    instructions: list = []
    checked_at: Optional[datetime] = None
    # `app_host` is what the CNAME has to point at, so the UI cannot render the record without it.
    # `checks` carries the per-record DNS outcome; the response model used to strip it, which meant
    # a failed verification came back with no explanation of why.
    app_host: Optional[str] = None
    checks: Optional[list] = None
