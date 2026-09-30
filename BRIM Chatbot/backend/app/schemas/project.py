from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.core.constants import PREDEFINED_INDUSTRIES

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    industry: str
    description: Optional[str] = None

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        if v not in PREDEFINED_INDUSTRIES:
            raise ValueError(f"Industry must be one of: {', '.join(PREDEFINED_INDUSTRIES)}")
        return v

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    industry: Optional[str] = None
    description: Optional[str] = None

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PREDEFINED_INDUSTRIES:
            raise ValueError(f"Industry must be one of: {', '.join(PREDEFINED_INDUSTRIES)}")
        return v

class ProjectResponse(ProjectBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
