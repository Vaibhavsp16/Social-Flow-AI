import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger("uvicorn")

def create_db_engine():
    db_url = settings.get_database_url()
    try:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        eng = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        # Test connection
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception as e:
        logger.warning(f"Could not connect to configured PostgreSQL ({db_url}): {e}")
        logger.info("Falling back to local SQLite database (brim_ai.db) for development...")
        fallback_url = "sqlite:///./brim_ai.db"
        return create_engine(fallback_url, connect_args={"check_same_thread": False})

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models import Base
    Base.metadata.create_all(bind=engine)
