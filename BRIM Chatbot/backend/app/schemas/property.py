from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PropertyOut(BaseModel):
    property_id: str
    title: str
    project_name: Optional[str] = None
    location: str
    city: Optional[str] = None
    property_type: str
    bhk: Optional[int] = None
    price: float
    price_display: str
    listing_type: str
    amenities: List[str] = []
    description: Optional[str] = None
    brochure_url: Optional[str] = None
    status: str
    is_mock: bool = True
    match_reasons: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class LeadOut(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    preferred_contact: Optional[str] = None
    requirements: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LeadDetail(LeadOut):
    bot_id: int
    conversation_id: Optional[int] = None
    intent: Optional[str] = None
    location: Optional[str] = None
    budget_max: Optional[int] = None
    status: str = "NEW"
    created_at: Optional[Any] = None


class PropertySearchResult(BaseModel):
    properties: List[PropertyOut] = Field(default_factory=list)
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
