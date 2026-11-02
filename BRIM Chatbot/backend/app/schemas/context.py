from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class GreetingRequest(BaseModel):
    """
    Browser-supplied context for the opening greeting.

    Only coarse values are accepted: a city/region label and the local hour. Coordinates are
    deliberately not part of this contract.
    """

    bot_id: Optional[int] = None
    language: Optional[str] = None
    language_hint: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    utc_offset_minutes: Optional[int] = Field(default=None, ge=-720, le=840)
    location_granted: bool = False
    seed: Optional[str] = Field(default=None, max_length=64)


class GreetingResponse(BaseModel):
    text: str
    language: str
    decision: str
    context: Dict[str, Any] = {}
