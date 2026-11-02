from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.bot import Bot
from app.models.lead import Lead
from app.models.project import Project
from app.models.property import Property
from app.models.user import User
from app.schemas.property import LeadDetail, PropertyOut
from app.services.property_service import PropertyService

router = APIRouter(tags=["Properties"])


def _owned_bot(db: Session, bot_id: int, user_id: int) -> Bot:
    bot = (
        db.query(Bot)
        .join(Project)
        .filter(Bot.id == bot_id, Project.user_id == user_id)
        .first()
    )
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found.")
    return bot


@router.get("/bots/{bot_id}/properties", response_model=List[PropertyOut])
def list_properties(
    bot_id: int,
    listing_type: Optional[str] = Query(default=None, pattern="^(SALE|RENT)$"),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The inventory the bot may talk about. Development data until a live feed is connected."""
    _owned_bot(db, bot_id, current_user.id)
    PropertyService.ensure_seeded(db, bot_id)

    query = db.query(Property).filter(Property.bot_id == bot_id)
    if listing_type:
        query = query.filter(Property.listing_type == listing_type)
    rows = query.order_by(Property.location, Property.price).limit(limit).all()
    return [PropertyService.to_dict(row) for row in rows]


@router.post("/bots/{bot_id}/properties/seed")
def seed_properties(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load the clearly-labelled development inventory (idempotent)."""
    _owned_bot(db, bot_id, current_user.id)
    inserted = PropertyService.ensure_seeded(db, bot_id)
    total = db.query(Property).filter(Property.bot_id == bot_id).count()
    return {
        "inserted": inserted,
        "total": total,
        "is_development_data": True,
        "notice": (
            "Illustrative records for the demo. Not real Prycoons listings, prices or availability."
        ),
    }


@router.get("/bots/{bot_id}/leads", response_model=List[LeadDetail])
def list_leads(
    bot_id: int,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leads captured by this bot's conversations, newest first."""
    _owned_bot(db, bot_id, current_user.id)
    rows = (
        db.query(Lead)
        .filter(Lead.bot_id == bot_id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        LeadDetail(
            id=lead.id,
            bot_id=lead.bot_id,
            conversation_id=lead.conversation_id,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            preferred_contact=lead.preferred_contact,
            requirements=lead.requirements,
            intent=lead.intent,
            location=lead.location,
            budget_max=lead.budget_max,
            status=lead.status,
            created_at=lead.created_at,
        )
        for lead in rows
    ]
