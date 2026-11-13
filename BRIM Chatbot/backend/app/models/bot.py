from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base

class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(50), default="English", nullable=False)
    personality = Column(String(100), default="Friendly & professional", nullable=False)
    welcome_message = Column(Text, default="Hi! How can I help you today?", nullable=False)
    status = Column(String(50), default="Live", nullable=False)
    shareable_slug = Column(String(255), unique=True, index=True, nullable=False)

    # ── What the bot is for ──────────────────────────────────────────────────
    # `primary_use_case` selects a behaviour playbook (see core/use_cases.py): it decides what the
    # bot drives toward, which follow-up it offers and what it must never do. Without it every bot
    # behaved identically regardless of why it was created.
    primary_use_case = Column(String(64), default="general_assistant", nullable=False)
    # How answers are shaped. Distinct from personality: personality is the voice, style is the
    # length/structure the visitor gets.
    response_style = Column(String(64), default="simple_clear", nullable=False)
    # when_relevant | always | never
    lead_collection = Column(String(32), default="when_relevant", nullable=False)
    # allow_when_needed | always_offer | disabled
    human_handoff = Column(String(32), default="allow_when_needed", nullable=False)
    # Ask for contact details once this many messages have been exchanged (0 disables).
    contact_after_messages = Column(Integer, default=3, nullable=False)
    # Prompt an idle visitor after this many seconds (0 disables).
    idle_prompt_seconds = Column(Integer, default=30, nullable=False)
    # Shown in contact prompts and embedding copy; falls back to the project name.
    company_name = Column(String(255), nullable=True)

    # ── Hosting ──────────────────────────────────────────────────────────────
    # The company keeps the domain in their own name; we only store the hostname, the verification
    # token they publish in DNS and the result of the last check.
    custom_domain = Column(String(255), unique=True, index=True, nullable=True)
    # none | pending | verified | failed
    domain_status = Column(String(32), default="none", nullable=False)
    domain_token = Column(String(64), nullable=True)
    domain_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def greeting_preview(self):
        """The first message a visitor actually sees, so the editor cannot disagree with chat."""
        # Imported here because the greeting service reads the message catalogue, which pulls in
        # settings; a module-level import would create a cycle through the model package.
        from app.services.greeting_service import GreetingService

        return GreetingService.preview(self.welcome_message, self.language)

    project = relationship("Project", back_populates="bots")
    knowledge_sources = relationship("KnowledgeSource", back_populates="bot", cascade="all, delete-orphan")
    chunks = relationship("KnowledgeChunk", back_populates="bot", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="bot", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="bot", cascade="all, delete-orphan")

