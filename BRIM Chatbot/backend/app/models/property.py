"""Property inventory used by the real-estate conversation flow.

Rows are scoped to a bot. Until a real Prycoons inventory feed exists, rows are marked
``is_mock=True`` so the UI can label them as development data and nobody mistakes them for
live listings.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.base import Base


class ListingType(str, enum.Enum):
    SALE = "SALE"
    RENT = "RENT"


class PropertyStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    SOLD = "SOLD"
    RENTED = "RENTED"
    UPCOMING = "UPCOMING"


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)

    property_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    project_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=False, index=True)
    city = Column(String(120), nullable=True)
    property_type = Column(String(64), nullable=False)  # Apartment / Villa / Plot / Penthouse
    bhk = Column(Integer, nullable=True)
    price = Column(Float, nullable=False)
    price_unit = Column(String(16), default="INR", nullable=False)
    listing_type = Column(String(16), default="SALE", nullable=False, index=True)
    amenities = Column(Text, default="[]", nullable=False)  # JSON array
    description = Column(Text, nullable=True)
    brochure_url = Column(String(512), nullable=True)
    status = Column(String(32), default="AVAILABLE", nullable=False, index=True)
    is_mock = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", backref="properties")
