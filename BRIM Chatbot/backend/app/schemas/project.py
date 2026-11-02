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

class ProjectResponse(BaseModel):
    """
    Read model, deliberately not reusing the write validator.

    Projects created before the industry list changed still carry their original value. A
    response validator would turn those rows into 500s for the whole project list; the UI is
    responsible for displaying a stored value that is no longer offered in the dropdown.
    """
    id: int
    user_id: int
    name: str
    industry: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
