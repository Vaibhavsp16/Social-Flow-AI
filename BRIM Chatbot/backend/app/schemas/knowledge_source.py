import json
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, HttpUrl, field_validator, model_validator
from app.core.constants import KnowledgeSourceType, ProcessingStatus

class WebsiteCreate(BaseModel):
    url: str = Field(..., description="Website URL to ingest")
    name: Optional[str] = None
    # 1 = only the given page. The default crawls the site, because a bot fed one page answers
    # nothing beyond it. Depth and a time budget still bound the work.
    max_pages: Optional[int] = Field(default=30, ge=1, le=40)
    # 0 = seed page only, 1 = its links, 2 = their links. Omitted means the crawler default.
    max_depth: Optional[int] = Field(default=None, ge=0, le=2)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("Website URL must start with http:// or https://")
        if len(v) < 8 or "." not in v:
            raise ValueError("Please provide a valid website domain URL")
        return v

class SocialLinkCreate(BaseModel):
    url: str = Field(..., description="Social media profile or post URL")
    platform: Optional[str] = None
    name: Optional[str] = None
    # Platforms routinely refuse server-side reads of a post. Pasting the caption guarantees
    # the content is answerable, and hashtags are parsed out of it automatically.
    caption: Optional[str] = Field(
        default=None,
        max_length=8000,
        description=(
            "Caption text copied from their posts. Separate multiple posts with a line of --- "
            "to store each as its own post with its own hashtags."
        ),
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("Social URL must start with http:// or https://")
        return v

class InstructionCreate(BaseModel):
    name: str = Field(default="Custom Business Instructions", min_length=2, max_length=200)
    instructions: str = Field(..., min_length=5, description="Primary business instructions and guidance")
    tone: Optional[str] = "Friendly & professional"
    restrictions: Optional[str] = None
    objectives: Optional[str] = None
    important_information: Optional[str] = None

class KnowledgeSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    instructions: Optional[str] = None
    tone: Optional[str] = None
    restrictions: Optional[str] = None
    objectives: Optional[str] = None

class KnowledgeSourceResponse(BaseModel):
    id: int
    bot_id: int
    source_type: str
    name: str
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    source_url: Optional[str] = None
    processing_status: str
    error_message: Optional[str] = None
    chunks_count: int = 0
    metadata_json: str = "{}"
    created_at: datetime
    updated_at: datetime
    extracted_text_preview: Optional[str] = None
    extracted_text: Optional[str] = None

    # Crawl coverage, lifted out of metadata_json so a client does not have to parse a string to
    # find out whether the site was actually read or only its homepage.
    pages_crawled: Optional[int] = None
    character_count: Optional[int] = None
    coverage_warning: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _lift_crawl_summary(self):
        try:
            data = json.loads(self.metadata_json or "{}")
        except (TypeError, ValueError):
            return self
        if isinstance(data, dict):
            self.pages_crawled = data.get("pages_crawled", self.pages_crawled)
            self.character_count = data.get("character_count", self.character_count)
            self.coverage_warning = data.get("coverage_warning", self.coverage_warning)
        return self
