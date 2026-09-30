from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.constants import PREDEFINED_INDUSTRIES
from app.database.session import init_db
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.bots import router as bots_router
from app.api.knowledge import router as knowledge_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router

# Initialize database tables
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development flexibility
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

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(bots_router, prefix=settings.API_V1_STR)
app.include_router(knowledge_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(conversations_router, prefix=settings.API_V1_STR)

