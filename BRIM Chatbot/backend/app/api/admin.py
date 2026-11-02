"""
Admin console API.

Access is gated by ``require_admin``; business accounts receive 403 on every route here. Lists
expose what an operator needs to support the platform (identity, ownership, counts, status) and
deliberately omit password hashes and end-customer contact details — lead phone/email are masked.
"""

from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.session import get_db
from app.models.activity import ActivityEvent
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.project import Project
from app.models.user import User
from app.services.analytics_service import AnalyticsService, parse_window
from app.services.reporting_service import ReportingService, _mask

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])

LIMIT = Query(default=100, ge=1, le=500)
OFFSET = Query(default=0, ge=0)


@router.get("/overview")
def admin_overview(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    window_start, window_end = parse_window(start, end)
    platform = AnalyticsService.platform_report(db, start, end)

    return {
        **platform,
        "entities": {
            "users": db.query(func.count(User.id)).scalar() or 0,
            "users_in_range": db.query(func.count(User.id))
            .filter(User.created_at >= window_start, User.created_at <= window_end)
            .scalar() or 0,
            "projects": db.query(func.count(Project.id)).scalar() or 0,
            "bots": db.query(func.count(Bot.id)).scalar() or 0,
            "conversations": db.query(func.count(Conversation.id)).scalar() or 0,
            "leads": db.query(func.count(Lead.id)).scalar() or 0,
            "activity_events": db.query(func.count(ActivityEvent.id)).scalar() or 0,
            "handoffs_open": db.query(func.count(Conversation.id))
            .filter(Conversation.status == "HANDOFF_REQUESTED")
            .scalar() or 0,
        },
    }


@router.get("/users")
def admin_users(
    limit: int = LIMIT,
    offset: int = OFFSET,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    project_counts = dict(
        db.query(Project.user_id, func.count(Project.id)).group_by(Project.user_id).all()
    )
    bot_counts = dict(
        db.query(Project.user_id, func.count(Bot.id))
        .join(Bot, Bot.project_id == Project.id)
        .group_by(Project.user_id)
        .all()
    )
    return {
        "total": db.query(func.count(User.id)).scalar() or 0,
        "items": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "created_at": user.created_at.isoformat(),
                "projects": project_counts.get(user.id, 0),
                "bots": bot_counts.get(user.id, 0),
            }
            for user in rows
        ],
    }


@router.get("/projects")
def admin_projects(
    limit: int = LIMIT,
    offset: int = OFFSET,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = (
        db.query(Project, User.email)
        .join(User, User.id == Project.user_id)
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    bot_counts = dict(
        db.query(Bot.project_id, func.count(Bot.id)).group_by(Bot.project_id).all()
    )
    return {
        "items": [
            {
                "id": project.id,
                "name": project.name,
                "industry": project.industry,
                "owner": owner_email,
                "created_at": project.created_at.isoformat(),
                "bots": bot_counts.get(project.id, 0),
            }
            for project, owner_email in rows
        ]
    }


@router.get("/bots")
def admin_bots(
    limit: int = LIMIT,
    offset: int = OFFSET,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = (
        db.query(Bot, Project.name, User.email)
        .join(Project, Project.id == Bot.project_id)
        .join(User, User.id == Project.user_id)
        .order_by(Bot.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    convo_counts = dict(
        db.query(Conversation.bot_id, func.count(Conversation.id))
        .group_by(Conversation.bot_id)
        .all()
    )
    return {
        "items": [
            {
                "id": bot.id,
                "name": bot.name,
                "status": bot.status,
                "project": project_name,
                "owner": owner_email,
                "created_at": bot.created_at.isoformat(),
                "conversations": convo_counts.get(bot.id, 0),
            }
            for bot, project_name, owner_email in rows
        ]
    }


@router.get("/conversations")
def admin_conversations(
    limit: int = LIMIT,
    offset: int = OFFSET,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = (
        db.query(Conversation, Bot.name, User.email)
        .join(Bot, Bot.id == Conversation.bot_id)
        .join(Project, Project.id == Bot.project_id)
        .join(User, User.id == Project.user_id)
        .order_by(Conversation.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    from app.models.conversation import Message

    message_counts = dict(
        db.query(Message.conversation_id, func.count(Message.id))
        .group_by(Message.conversation_id)
        .all()
    )
    return {
        "items": [
            {
                "id": convo.id,
                "bot": bot_name,
                "owner": owner_email,
                "session_id": convo.session_id,
                "intent": convo.intent,
                "status": convo.status,
                "started_at": convo.started_at.isoformat(),
                "messages": message_counts.get(convo.id, 0),
            }
            for convo, bot_name, owner_email in rows
        ]
    }


@router.get("/leads")
def admin_leads(
    limit: int = LIMIT,
    offset: int = OFFSET,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = (
        db.query(Lead, Bot.name, User.email)
        .join(Bot, Bot.id == Lead.bot_id)
        .join(Project, Project.id == Bot.project_id)
        .join(User, User.id == Project.user_id)
        .order_by(Lead.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": db.query(func.count(Lead.id)).scalar() or 0,
        "items": [
            {
                "id": lead.id,
                "created_at": lead.created_at.isoformat(),
                "bot": bot_name,
                "owner": owner_email,
                "name": lead.name,
                # End-customer contact details stay masked in the platform console.
                "phone": _mask(lead.phone, 4),
                "email": _mask(lead.email, 6),
                "preferred_contact": lead.preferred_contact,
                "intent": lead.intent,
                "location": lead.location,
                "status": lead.status,
            }
            for lead, bot_name, owner_email in rows
        ],
    }


@router.get("/activity")
def admin_activity(
    limit: int = LIMIT,
    offset: int = OFFSET,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(ActivityEvent, User.email).outerjoin(User, User.id == ActivityEvent.user_id)
    if event_type:
        query = query.filter(ActivityEvent.event_type == event_type)
    rows = query.order_by(ActivityEvent.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "actor": actor_email,
                "created_at": event.created_at.isoformat(),
            }
            for event, actor_email in rows
        ]
    }


@router.get("/reports/{kind}")
def admin_report(
    kind: str,
    format: str = Query(default="json", pattern="^(json|csv|pdf)$"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    bot_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Platform-wide report. CSV output uses the same rows as the JSON view."""
    if kind not in ReportingService.KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown report: {kind}")

    report = ReportingService.build(db, kind, start=start, end=end, bot_id=bot_id, user_id=None)
    if format == "csv":
        payload = ("\ufeff" + ReportingService.to_csv(report)).encode("utf-8")
        return StreamingResponse(
            BytesIO(payload),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{ReportingService.filename(report)}"'
            },
        )

    if format == "pdf":
        filename = ReportingService.filename(report).replace(".csv", ".pdf")
        return StreamingResponse(
            BytesIO(ReportingService.to_pdf(report)),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return report
