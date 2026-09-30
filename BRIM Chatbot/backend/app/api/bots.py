from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.bot import BotCreate, BotUpdate, BotResponse
from app.services.bot_service import BotService
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/bots", tags=["Bots"])

@router.post("", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
def create_bot(
    bot_in: BotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new bot under an owned project.
    """
    return BotService.create_bot(db=db, bot_in=bot_in, user_id=current_user.id)

@router.get("", response_model=List[BotResponse])
def get_user_bots(
    project_id: Optional[int] = Query(None, description="Filter bots by project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all bots belonging to projects owned by the authenticated user.
    """
    return BotService.get_user_bots(db=db, user_id=current_user.id, project_id=project_id)

@router.get("/{bot_id}", response_model=BotResponse)
def get_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific bot by ID.
    """
    return BotService.get_bot_by_id(db=db, bot_id=bot_id, user_id=current_user.id)

@router.put("/{bot_id}", response_model=BotResponse)
def update_bot(
    bot_id: int,
    bot_in: BotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update bot details.
    """
    return BotService.update_bot(
        db=db, bot_id=bot_id, bot_in=bot_in, user_id=current_user.id
    )

@router.delete("/{bot_id}")
def delete_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a bot.
    """
    return BotService.delete_bot(db=db, bot_id=bot_id, user_id=current_user.id)
