"""Leads and meetings for the business that owns the bot.

This is the screen the sales team actually works from, so it exposes the real phone number and the
time the person asked to be called. The admin console keeps masking contact details; this router
never serves admin scope.
"""

from datetime import date
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.bot import Bot
from app.models.lead import Lead, LeadStatus
from app.models.meeting import Meeting, MeetingStatus
from app.models.project import Project
from app.models.user import User
from app.services import contact_service

router = APIRouter(tags=["Leads & Meetings"])


def _owned_bot(db: Session, bot_id: int, user: User) -> Bot:
    bot = (
        db.query(Bot)
        .join(Project, Project.id == Bot.project_id)
        .filter(Bot.id == bot_id, Project.user_id == user.id)
        .first()
    )
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found.")
    return bot


class LeadStatusUpdate(BaseModel):
    status: str = Field(..., description="NEW | CONTACTED | QUALIFIED | CLOSED")


class MeetingStatusUpdate(BaseModel):
    status: str = Field(..., description="REQUESTED | CONFIRMED | COMPLETED | CANCELLED")


# `GET /bots/{bot_id}/leads` is owned by api/properties.py and returns LeadDetail rows; it serves
# every industry, not just real estate, so the richer fields were added there rather than shipping a
# second endpoint on the same path that silently shadows the first.


@router.get("/bots/{bot_id}/leads.csv")
def download_leads(
    bot_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leads as a CSV file the team can open in Excel."""
    bot = _owned_bot(db, bot_id, current_user)
    payload, filename = contact_service.leads_csv(
        db, bot_id=bot.id, user_id=current_user.id, start=start, end=end
    )
    return StreamingResponse(
        BytesIO(("\ufeff" + payload).encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads/export.csv")
def download_all_leads(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every lead across the caller's bots, for the analytics page."""
    payload, filename = contact_service.leads_csv(
        db, user_id=current_user.id, start=start, end=end
    )
    return StreamingResponse(
        BytesIO(("\ufeff" + payload).encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/leads/{lead_id}")
def update_lead_status(
    lead_id: int,
    payload: LeadStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a lead through the pipeline (called / qualified / closed)."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    _owned_bot(db, lead.bot_id, current_user)

    allowed = {item.value for item in LeadStatus}
    if payload.status.upper() not in allowed:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(sorted(allowed))}")
    lead.status = payload.status.upper()
    db.commit()
    db.refresh(lead)
    return {"id": lead.id, "status": lead.status}


@router.get("/bots/{bot_id}/meetings")
def list_meetings(
    bot_id: int,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calls and visits the bot arranged, newest first."""
    _owned_bot(db, bot_id, current_user)
    meetings = (
        db.query(Meeting)
        .filter(Meeting.bot_id == bot_id)
        .order_by(Meeting.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(meetings),
        "meetings": [
            {
                "id": meeting.id,
                "lead_id": meeting.lead_id,
                "conversation_id": meeting.conversation_id,
                "name": meeting.name,
                "phone": meeting.phone,
                "email": meeting.email,
                "mode": meeting.mode,
                "preferred_slot": meeting.preferred_slot,
                "scheduled_for": meeting.scheduled_for.isoformat() if meeting.scheduled_for else None,
                "timezone": meeting.timezone,
                "status": meeting.status,
                "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            }
            for meeting in meetings
        ],
    }


@router.patch("/meetings/{meeting_id}")
def update_meeting_status(
    meeting_id: int,
    payload: MeetingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    _owned_bot(db, meeting.bot_id, current_user)

    allowed = {item.value for item in MeetingStatus}
    if payload.status.upper() not in allowed:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(sorted(allowed))}")
    meeting.status = payload.status.upper()
    db.commit()
    db.refresh(meeting)
    return {"id": meeting.id, "status": meeting.status}
