from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    # Nullable: a Google-only account never sets a local password. Password login is skipped for
    # those rows instead of comparing against an empty hash.
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), default="BUSINESS", nullable=False)

    # ── Identity providers ───────────────────────────────────────────────────
    google_id = Column(String(255), unique=True, index=True, nullable=True)
    avatar_url = Column(String(1000), nullable=True)
    # local | google  — which provider the account was first created with. An account created
    # locally can later sign in with Google; the link is by verified email.
    auth_provider = Column(String(32), default="local", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
