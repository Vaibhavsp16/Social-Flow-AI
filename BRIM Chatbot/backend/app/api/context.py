from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.bot import Bot
from app.models.project import Project
from app.schemas.context import GreetingRequest, GreetingResponse
from app.services.greeting_service import GreetingService
from app.services.language_service import LanguageService

router = APIRouter(tags=["Context"])


@router.get("/context/languages")
def list_languages():
    """Languages the assistant can reply in."""
    return {
        "languages": [
            {"code": code, "label": label}
            for code, label in LanguageService.supported().items()
        ],
        "default": "en",
    }


@router.post("/context/greeting", response_model=GreetingResponse)
def build_greeting(payload: GreetingRequest, db: Session = Depends(get_db)):
    """
    Build a greeting from whatever context the browser is allowed to share.

    Public on purpose: it is called before login on an embedded widget. It never reads or
    stores location; a missing city simply means the greeting uses time of day only.
    """
    # Unknown caller: a neutral name, never a hard-coded client. When a bot is supplied, both
    # its name and its industry drive the greeting (property phrasing only for Real Estate).
    bot_name = "your assistant"
    industry = None
    if payload.bot_id:
        bot = db.query(Bot).filter(Bot.id == payload.bot_id).first()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found.")
        bot_name = bot.name
        industry = getattr(getattr(bot, "project", None), "industry", None)

    greeting = GreetingService.build(
        bot_name=bot_name,
        industry=industry,
        language=payload.language,
        language_hint=payload.language_hint,
        city=payload.city,
        region=payload.region,
        local_hour=payload.local_hour,
        utc_offset_minutes=payload.utc_offset_minutes,
        seed=payload.seed or (f"bot-{payload.bot_id}" if payload.bot_id else "greeting"),
    )
    return GreetingResponse(
        text=greeting["text"],
        language=greeting["language"],
        decision=greeting["decision"],
        context=greeting["context"],
    )
