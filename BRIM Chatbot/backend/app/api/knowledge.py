from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.knowledge_source import (
    WebsiteCreate,
    SocialLinkCreate,
    InstructionCreate,
    KnowledgeSourceUpdate,
    KnowledgeSourceResponse,
)
from app.services.knowledge_service import KnowledgeService
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(tags=["Knowledge Sources"])

@router.get("/bots/{bot_id}/knowledge", response_model=List[KnowledgeSourceResponse])
def list_bot_knowledge_sources(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all knowledge sources associated with a specific bot.
    """
    return KnowledgeService.list_bot_sources(db=db, bot_id=bot_id, user_id=current_user.id)

@router.post("/bots/{bot_id}/knowledge/upload", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    bot_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and extract a document (PDF, DOC, DOCX, TXT) or image (PNG, JPG, WEBP).
    """
    return await KnowledgeService.upload_file(db=db, bot_id=bot_id, file=file, user_id=current_user.id)

@router.post("/bots/{bot_id}/knowledge/website", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
def add_website_knowledge(
    bot_id: int,
    website_in: WebsiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add and scrape a website URL for chatbot knowledge.
    """
    return KnowledgeService.add_website(db=db, bot_id=bot_id, website_in=website_in, user_id=current_user.id)

@router.post("/knowledge/websites", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
def add_website_direct(
    bot_id: int = Form(...),
    url: str = Form(...),
    name: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Direct endpoint for adding a website URL.
    """
    website_in = WebsiteCreate(url=url, name=name)
    return KnowledgeService.add_website(db=db, bot_id=bot_id, website_in=website_in, user_id=current_user.id)

@router.post("/bots/{bot_id}/knowledge/social", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
def add_social_link(
    bot_id: int,
    social_in: SocialLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a social media profile URL for future automated ingestion.
    """
    return KnowledgeService.add_social_link(db=db, bot_id=bot_id, social_in=social_in, user_id=current_user.id)

@router.post("/bots/{bot_id}/knowledge/instruction", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
def add_instructions(
    bot_id: int,
    instr_in: InstructionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Configure custom business prompts, tone, restrictions, and objectives.
    """
    return KnowledgeService.add_instructions(db=db, bot_id=bot_id, instr_in=instr_in, user_id=current_user.id)

@router.get("/knowledge/{source_id}", response_model=KnowledgeSourceResponse)
def get_knowledge_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific knowledge source.
    """
    return KnowledgeService.get_knowledge_source_by_id(db=db, source_id=source_id, user_id=current_user.id)

@router.put("/knowledge/{source_id}", response_model=KnowledgeSourceResponse)
def update_knowledge_source(
    source_id: int,
    source_in: KnowledgeSourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a knowledge source.
    """
    return KnowledgeService.update_source(db=db, source_id=source_id, source_in=source_in, user_id=current_user.id)

@router.delete("/knowledge/{source_id}")
def delete_knowledge_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a knowledge source and its stored file.
    """
    return KnowledgeService.delete_source(db=db, source_id=source_id, user_id=current_user.id)

@router.get("/knowledge/samples")
def get_sample_knowledge_documents():
    """
    List pre-packaged industry demo knowledge documents.
    """
    return KnowledgeService.get_sample_documents()

@router.post("/bots/{bot_id}/knowledge/seed-sample", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
def seed_sample_knowledge_source(
    bot_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Seed an official demo knowledge document (Real Estate, Healthcare, SaaS) into the bot's knowledge base.
    """
    sample_key = payload.get("sample_key", "real_estate")
    return KnowledgeService.seed_sample_document(db=db, bot_id=bot_id, sample_key=sample_key, user_id=current_user.id)
