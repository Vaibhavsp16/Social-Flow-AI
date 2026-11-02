"""
Property inventory and matching.

The database is the source of truth for what the bot may say. Until a real Prycoons feed exists,
the inventory is the clearly-labelled development data in demo_documents/prycoons_properties.json,
loaded per bot on first use. The LLM never invents listings: it only describes the rows returned
by ``search``.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.property import ListingType, Property, PropertyStatus

logger = logging.getLogger(__name__)

# Buyer/renter vocabulary that should map onto stored property types.
PROPERTY_TYPE_ALIASES = {
    "flat": "Apartment",
    "apartment": "Apartment",
    "builder floor": "Apartment",
    "villa": "Villa",
    "bungalow": "Villa",
    "row house": "Villa",
    "plot": "Plot",
    "land": "Plot",
    "penthouse": "Penthouse",
}


def format_price(price: float, listing_type: str) -> str:
    """₹1.85 Cr for sale prices, ₹32,000/month for rentals."""
    if listing_type == ListingType.RENT.value:
        return f"₹{int(price):,}/month"
    if price >= 10_000_000:
        value = price / 10_000_000
        return f"₹{value:.2f} Cr".replace(".00 Cr", " Cr")
    if price >= 100_000:
        value = price / 100_000
        return f"₹{value:.1f} L".replace(".0 L", " L")
    return f"₹{int(price):,}"


class PropertyService:

    SEED_FILENAME = "prycoons_properties.json"

    @classmethod
    def _seed_path(cls) -> Path:
        from app.services.knowledge_service import KnowledgeService

        return KnowledgeService._industry_pack_dir().parent / cls.SEED_FILENAME

    @classmethod
    def ensure_seeded(cls, db: Session, bot_id: int) -> int:
        """Load the development inventory for a bot once. Returns rows inserted."""
        existing = db.query(Property).filter(Property.bot_id == bot_id).count()
        if existing:
            return 0

        path = cls._seed_path()
        if not path.exists():
            logger.warning(f"Property seed file missing at {path}")
            return 0

        payload = json.loads(path.read_text(encoding="utf-8"))
        inserted = 0
        for row in payload.get("properties", []):
            db.add(
                Property(
                    bot_id=bot_id,
                    property_id=row["property_id"],
                    title=row["title"],
                    project_name=row.get("project_name"),
                    location=row["location"],
                    city=row.get("city"),
                    property_type=row["property_type"],
                    bhk=row.get("bhk"),
                    price=float(row["price"]),
                    listing_type=row.get("listing_type", ListingType.SALE.value),
                    amenities=json.dumps(row.get("amenities", [])),
                    description=row.get("description"),
                    brochure_url=row.get("brochure_url"),
                    status=row.get("status", PropertyStatus.AVAILABLE.value),
                    is_mock=True,
                )
            )
            inserted += 1
        db.commit()
        logger.info(f"Seeded {inserted} development properties for bot {bot_id}")
        return inserted

    @staticmethod
    def _normalise_type(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return PROPERTY_TYPE_ALIASES.get(value.strip().lower(), value.strip().title())

    @classmethod
    def to_dict(cls, prop: Property, match_reasons: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            amenities = json.loads(prop.amenities or "[]")
        except (json.JSONDecodeError, TypeError):
            amenities = []
        return {
            "property_id": prop.property_id,
            "title": prop.title,
            "project_name": prop.project_name,
            "location": prop.location,
            "city": prop.city,
            "property_type": prop.property_type,
            "bhk": prop.bhk,
            "price": prop.price,
            "price_display": format_price(prop.price, prop.listing_type),
            "listing_type": prop.listing_type,
            "amenities": amenities,
            "description": prop.description,
            "brochure_url": prop.brochure_url,
            "status": prop.status,
            "is_mock": bool(prop.is_mock),
            "match_reasons": match_reasons or [],
        }

    @classmethod
    def search(
        cls,
        db: Session,
        bot_id: int,
        listing_type: str = ListingType.SALE.value,
        location: Optional[str] = None,
        property_type: Optional[str] = None,
        bhk: Optional[int] = None,
        budget_max: Optional[int] = None,
        amenities: Optional[Iterable[str]] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Filter → rank → shortlist.

        Hard filters: listing type, availability, property type and BHK. Location matches on
        substring so "Ambli" finds "Ambli Road". Budget is soft: when nothing fits, the closest
        options are returned with an over-budget note instead of an empty list.
        """
        query = db.query(Property).filter(
            Property.bot_id == bot_id,
            Property.status == PropertyStatus.AVAILABLE.value,
            Property.listing_type == listing_type,
        )
        rows = query.all()
        if not rows:
            return []

        wanted_type = cls._normalise_type(property_type)
        if wanted_type:
            rows = [r for r in rows if (r.property_type or "").lower() == wanted_type.lower()]
        if bhk:
            rows = [r for r in rows if r.bhk == bhk]
        if not rows:
            return []

        location_key = (location or "").strip().lower()
        wanted_amenities = [a.lower() for a in (amenities or [])]

        if location_key:
            located = [
                r for r in rows
                if location_key in (r.location or "").lower() or (r.location or "").lower() in location_key
            ]
            if located:
                rows = located
            # No exact area match: keep the rest, they are still valid options to discuss.

        scored: List[tuple[Property, int, List[str]]] = []
        for prop in rows:
            score, reasons = 0, []
            if location_key and (
                location_key in (prop.location or "").lower()
                or (prop.location or "").lower() in location_key
            ):
                score += 3
                reasons.append(f"in {prop.location}")
            if wanted_type and (prop.property_type or "").lower() == wanted_type.lower():
                score += 2
                reasons.append(prop.property_type)
            if bhk and prop.bhk == bhk:
                score += 3
                reasons.append(f"{prop.bhk} BHK")
            if budget_max:
                if prop.price <= budget_max * 1.05:
                    score += 3
                    reasons.append("within budget")
                elif prop.price <= budget_max * 1.2:
                    score += 1
                    reasons.append("slightly above budget")
            try:
                prop_amenities = [a.lower() for a in json.loads(prop.amenities or "[]")]
            except (json.JSONDecodeError, TypeError):
                prop_amenities = []
            overlap = [a for a in wanted_amenities if a in prop_amenities]
            if overlap:
                score += len(overlap)
                reasons.append("has " + ", ".join(overlap))
            scored.append((prop, score, reasons))

        scored.sort(key=lambda item: (-item[1], item[0].price))
        return [cls.to_dict(prop, reasons) for prop, _score, reasons in scored[:limit]]

    @staticmethod
    def describe_shortlist(
        properties: List[Dict[str, Any]], intent: str, language: str = "en"
    ) -> str:
        """Deterministic summary text; the numbers come from the database, never from a model."""
        from app.core.messages import translate

        if not properties:
            return translate(language, "no_match")

        verb = translate(language, "verb_rent" if intent == "renting" else "verb_sale")
        if len(properties) == 1:
            lines = [translate(language, "shortlist_one", verb=verb)]
        else:
            lines = [translate(language, "shortlist_many", count=len(properties), verb=verb)]

        amenity_label = translate(language, "amenities_label")
        for index, prop in enumerate(properties, 1):
            bhk = f"{prop['bhk']} BHK " if prop.get("bhk") else ""
            amenities = ", ".join(prop["amenities"][:4])
            line = (
                f"{index}. {prop['title']} — {bhk}{prop['property_type']} in {prop['location']}, "
                f"{prop['price_display']}"
            )
            if amenities:
                line += f". {amenity_label}: {amenities}"
            lines.append(line)
        lines.append(translate(language, "shortlist_followup"))
        return "\n".join(lines)
