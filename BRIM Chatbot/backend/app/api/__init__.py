from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.bots import router as bots_router
from app.api.knowledge import router as knowledge_router

__all__ = ["auth_router", "projects_router", "bots_router", "knowledge_router"]
