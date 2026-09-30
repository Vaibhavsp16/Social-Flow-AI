import re
import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from app.models.bot import Bot
from app.models.project import Project
from app.schemas.bot import BotCreate, BotUpdate

def generate_slug(name: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', name).strip().lower()
    slug = re.sub(r'[\s_]+', '-', cleaned)
    if not slug:
        slug = f"bot-{uuid.uuid4().hex[:6]}"
    return slug

class BotService:
    @staticmethod
    def generate_unique_slug(db: Session, name: str) -> str:
        base_slug = generate_slug(name)
        slug = base_slug
        counter = 1
        while db.query(Bot).filter(Bot.shareable_slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    @staticmethod
    def get_user_bots(db: Session, user_id: int, project_id: int | None = None) -> list[Bot]:
        query = db.query(Bot).options(joinedload(Bot.project)).join(Project).filter(Project.user_id == user_id)
        if project_id is not None:
            query = query.filter(Bot.project_id == project_id)
        return query.order_by(Bot.created_at.desc()).all()

    @staticmethod
    def get_bot_by_id(db: Session, bot_id: int, user_id: int) -> Bot:
        bot = db.query(Bot).options(joinedload(Bot.project)).join(Project).filter(Bot.id == bot_id, Project.user_id == user_id).first()
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found or you do not have permission to access it."
            )
        return bot

    @staticmethod
    def create_bot(db: Session, bot_in: BotCreate, user_id: int) -> Bot:
        # Verify project belongs to user
        project = db.query(Project).filter(Project.id == bot_in.project_id, Project.user_id == user_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you do not have permission to add a bot to this project."
            )
        
        # Generate slug
        slug = bot_in.shareable_slug
        if not slug:
            slug = BotService.generate_unique_slug(db, bot_in.name)
        else:
            existing = db.query(Bot).filter(Bot.shareable_slug == slug).first()
            if existing:
                slug = BotService.generate_unique_slug(db, bot_in.name)

        db_bot = Bot(
            project_id=bot_in.project_id,
            name=bot_in.name.strip(),
            description=bot_in.description.strip() if bot_in.description else None,
            language=bot_in.language or "English",
            personality=bot_in.personality or "Friendly & professional",
            welcome_message=bot_in.welcome_message or "Hi! How can I help you today?",
            status=bot_in.status or "Live",
            shareable_slug=slug
        )
        db.add(db_bot)
        db.commit()
        db.refresh(db_bot)
        return db_bot

    @staticmethod
    def update_bot(db: Session, bot_id: int, bot_in: BotUpdate, user_id: int) -> Bot:
        bot = BotService.get_bot_by_id(db, bot_id, user_id)
        if bot_in.name is not None:
            bot.name = bot_in.name.strip()
        if bot_in.industry is not None and bot.project:
            bot.project.industry = bot_in.industry
        if bot_in.description is not None:
            bot.description = bot_in.description.strip()
        if bot_in.language is not None:
            bot.language = bot_in.language
        if bot_in.personality is not None:
            bot.personality = bot_in.personality
        if bot_in.welcome_message is not None:
            bot.welcome_message = bot_in.welcome_message.strip()
        if bot_in.status is not None:
            bot.status = bot_in.status
        if bot_in.shareable_slug is not None:
            # Check uniqueness if changed
            new_slug = bot_in.shareable_slug.strip().lower()
            if new_slug != bot.shareable_slug:
                existing = db.query(Bot).filter(Bot.shareable_slug == new_slug).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This shareable slug is already in use."
                    )
                bot.shareable_slug = new_slug
        
        db.commit()
        db.refresh(bot)
        return bot

    @staticmethod
    def delete_bot(db: Session, bot_id: int, user_id: int) -> dict:
        bot = BotService.get_bot_by_id(db, bot_id, user_id)
        db.delete(bot)
        db.commit()
        return {"message": "Bot deleted successfully", "id": bot_id}
