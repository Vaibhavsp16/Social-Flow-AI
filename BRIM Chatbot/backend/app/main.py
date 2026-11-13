from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.constants import PREDEFINED_INDUSTRIES
from app.core.rate_limit import RateLimitMiddleware
from app.core.use_cases import (
    HANDOFF_POLICIES,
    LEAD_POLICIES,
    RESPONSE_STYLES,
    use_cases_payload,
)
from app.database.session import init_db
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.bots import router as bots_router
from app.api.knowledge import router as knowledge_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.properties import router as properties_router
from app.api.context import router as context_router
from app.api.analytics import router as analytics_router
from app.api.admin import router as admin_router
from app.api.leads import router as leads_router
from app.api.public import router as public_router

# Initialize database tables
init_db()


def _host_is_verified_bot(host: str) -> bool:
    """Does this hostname belong to a verified custom domain?

    Called by the CORS layer for origins that are not in the static allow-list, so a chatbot served
    from the customer's own domain can still call the API from the browser.
    """
    from app.database.session import SessionLocal
    from app.models.bot import Bot

    session = SessionLocal()
    try:
        return (
            session.query(Bot.id)
            .filter(Bot.custom_domain == host, Bot.domain_status == "verified")
            .first()
            is not None
        )
    finally:
        session.close()


class BotAwareCORSMiddleware(CORSMiddleware):
    """CORS that also accepts a customer's own verified domain.

    A fixed origin list cannot contain domains that are added later, and opening ``*`` would break
    the credentialed requests the app relies on. So origins outside the list are only allowed when
    they are a verified custom domain, cached for a minute.
    """

    def is_allowed_origin(self, origin: str) -> bool:
        if super().is_allowed_origin(origin):
            return True
        from app.services import domain_service

        return domain_service.is_verified_origin(origin, _host_is_verified_bot)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS.
# An explicit origin list is required: "Access-Control-Allow-Origin: *" is not valid together
# with credentials, and the browser sends the JWT in the Authorization header.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    BotAwareCORSMiddleware,
    allow_origins=settings.cors_origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health checks
@app.get("/")
def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get(f"{settings.API_V1_STR}/industries")
def get_industries():
    """
    Returns the centralized list of predefined industries.
    """
    return {"industries": PREDEFINED_INDUSTRIES}


@app.get(f"{settings.API_V1_STR}/options")
def get_options():
    """Everything the bot builder needs to render its pickers, straight from the source of truth.

    Without this the wizard would hardcode its own copy of the use cases and styles and drift from
    what the prompt layer actually understands.
    """
    return {
        "use_cases": use_cases_payload(),
        "response_styles": [
            {"key": key, "label": key.replace("_", " ").title()} for key in RESPONSE_STYLES
        ],
        "lead_policies": list(LEAD_POLICIES),
        "handoff_policies": list(HANDOFF_POLICIES),
        "frontend_base_url": settings.frontend_url,
        "google_enabled": bool(settings.GOOGLE_CLIENT_ID),
    }

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(bots_router, prefix=settings.API_V1_STR)
app.include_router(knowledge_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(conversations_router, prefix=settings.API_V1_STR)
app.include_router(properties_router, prefix=settings.API_V1_STR)
app.include_router(context_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(leads_router, prefix=settings.API_V1_STR)
app.include_router(public_router, prefix=settings.API_V1_STR)
