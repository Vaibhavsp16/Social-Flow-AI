from datetime import date
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.bot import Bot
from app.models.project import Project
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.reporting_service import ReportingService

router = APIRouter(tags=["Analytics"])


def _owned_bot(db: Session, bot_id: int, user: User) -> Bot:
    bot = (
        db.query(Bot)
        .join(Project, Project.id == Bot.project_id)
        .filter(Bot.id == bot_id, Project.user_id == user.id)
        .first()
    )
    if not bot:
        # 404 rather than 403: do not confirm that another tenant's bot exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found.")
    return bot


@router.get("/analytics/overview")
def analytics_overview(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate metrics across the caller's own bots."""
    return AnalyticsService.platform_report(db, start, end, user_id=current_user.id)


@router.get("/analytics/bots/{bot_id}")
def bot_analytics(
    bot_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bot analytics: totals, intents, volume, knowledge and unanswered questions."""
    bot = _owned_bot(db, bot_id, current_user)
    return AnalyticsService.bot_report(db, bot.id, start, end)


@router.get("/reports/{kind}")
def build_report(
    kind: str,
    format: str = Query(default="json", pattern="^(json|csv|pdf)$"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    bot_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Report data (JSON) or a CSV download, scoped to the caller's own bots.
    """
    if kind not in ReportingService.KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown report: {kind}")

    if bot_id is not None:
        _owned_bot(db, bot_id, current_user)

    report = ReportingService.build(
        db, kind, start=start, end=end, bot_id=bot_id, user_id=current_user.id
    )

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
