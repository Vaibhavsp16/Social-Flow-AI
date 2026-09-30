import os
import uuid
import json
import logging
from typing import List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile, status
from app.models.knowledge_source import KnowledgeSource
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.bot import Bot
from app.models.project import Project
from app.core.constants import (
    KnowledgeSourceType,
    ProcessingStatus,
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_FILE_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)
from app.schemas.knowledge_source import (
    WebsiteCreate,
    SocialLinkCreate,
    InstructionCreate,
    KnowledgeSourceUpdate,
)
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# Uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class KnowledgeService:
    @staticmethod
    def verify_bot_ownership(db: Session, bot_id: int, user_id: int) -> Bot:
        """
        Verify that the bot exists and belongs to a project owned by user_id.
        """
        bot = db.query(Bot).join(Project).filter(Bot.id == bot_id, Project.user_id == user_id).first()
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found or you do not have permission to access it."
            )
        return bot

    @staticmethod
    def get_knowledge_source_by_id(db: Session, source_id: int, user_id: int) -> KnowledgeSource:
        """
        Retrieve a knowledge source by ID verifying ownership through Bot -> Project -> User.
        """
        source = (
            db.query(KnowledgeSource)
            .join(Bot)
            .join(Project)
            .filter(KnowledgeSource.id == source_id, Project.user_id == user_id)
            .first()
        )
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge source not found or you do not have permission to access it."
            )
        return source

    @staticmethod
    def list_bot_sources(db: Session, bot_id: int, user_id: int) -> List[KnowledgeSource]:
        """
        List all knowledge sources for a bot.
        """
        KnowledgeService.verify_bot_ownership(db, bot_id, user_id)
        return (
            db.query(KnowledgeSource)
            .filter(KnowledgeSource.bot_id == bot_id)
            .order_by(KnowledgeSource.created_at.desc())
            .all()
        )

    @staticmethod
    def _generate_and_save_chunks(
        db: Session,
        bot_id: int,
        source: KnowledgeSource,
        chunks: List[str],
        metadata: dict
    ):
        """
        Delete previous chunks for this source (if any) and insert newly embedded chunks.
        """
        db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).delete()

        for idx, chunk_text in enumerate(chunks):
            if not chunk_text or not chunk_text.strip():
                continue
            embedding = EmbeddingService.get_embedding(chunk_text)
            page_info = None
            if source.source_type == KnowledgeSourceType.DOCUMENT.value and metadata.get("page_count"):
                page_info = f"Section {idx + 1}"
            elif metadata.get("platform"):
                page_info = f"Profile: {metadata['platform']}"

            chunk_record = KnowledgeChunk(
                bot_id=bot_id,
                knowledge_source_id=source.id,
                chunk_index=idx,
                content=chunk_text.strip(),
                source_type=source.source_type,
                source_name=source.name,
                source_url=source.source_url,
                page_number=page_info,
                metadata_json=json.dumps(metadata),
                embedding_json=json.dumps(embedding),
            )
            db.add(chunk_record)
        db.commit()

    @staticmethod
    async def upload_file(
        db: Session,
        bot_id: int,
        file: UploadFile,
        user_id: int
    ) -> KnowledgeSource:
        """
        Securely validate, save, and process a document or image file.
        """
        bot = KnowledgeService.verify_bot_ownership(db, bot_id, user_id)

        filename = file.filename or "uploaded_file"
        file_ext = Path(filename).suffix.lower()

        # 1. Validation
        if file_ext not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{file_ext}'. Allowed types: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}"
            )

        # Read file contents
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty."
            )

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."
            )

        # Determine source type
        source_type = (
            KnowledgeSourceType.IMAGE.value
            if file_ext in ALLOWED_IMAGE_EXTENSIONS
            else KnowledgeSourceType.DOCUMENT.value
        )

        # 2. Secure Storage (UUID filename to prevent directory traversal / overwrite)
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        storage_path = UPLOAD_DIR / unique_filename

        with open(storage_path, "wb") as f:
            f.write(content)

        # 3. Create Database Record
        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=source_type,
            name=filename,
            original_filename=filename,
            file_path=str(storage_path),
            file_size=file_size,
            processing_status=ProcessingStatus.PROCESSING.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        # 4. Process and Extract
        try:
            extracted_text = ""
            metadata = {}

            if file_ext == ".pdf":
                extracted_text, metadata = DocumentProcessor.extract_from_pdf(str(storage_path))
            elif file_ext in [".doc", ".docx"]:
                extracted_text, metadata = DocumentProcessor.extract_from_docx(str(storage_path))
            elif file_ext == ".txt":
                extracted_text, metadata = DocumentProcessor.extract_from_txt(str(storage_path))
            elif file_ext in ALLOWED_IMAGE_EXTENSIONS:
                extracted_text, metadata = DocumentProcessor.extract_from_image(str(storage_path))

            chunks = DocumentProcessor.chunk_text(extracted_text)

            source.extracted_text = extracted_text
            source.chunks_count = len(chunks)
            source.metadata_json = json.dumps(metadata)
            source.processing_status = ProcessingStatus.COMPLETED.value
            source.error_message = None
            db.commit()

            # Generate and persist chunks + vector embeddings
            KnowledgeService._generate_and_save_chunks(db, bot_id, source, chunks, metadata)

        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}", exc_info=True)
            source.processing_status = ProcessingStatus.FAILED.value
            source.error_message = f"Extraction failed: {str(e)}"
            db.commit()

        db.refresh(source)
        return source

    @staticmethod
    def add_website(
        db: Session,
        bot_id: int,
        website_in: WebsiteCreate,
        user_id: int
    ) -> KnowledgeSource:
        """
        Validate URL, scrape content, and create website knowledge source.
        """
        KnowledgeService.verify_bot_ownership(db, bot_id, user_id)

        name = website_in.name or website_in.url

        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=KnowledgeSourceType.WEBSITE.value,
            name=name,
            source_url=website_in.url,
            processing_status=ProcessingStatus.PROCESSING.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        try:
            extracted_text, metadata = DocumentProcessor.extract_from_website(website_in.url)
            chunks = DocumentProcessor.chunk_text(extracted_text)

            if not website_in.name and metadata.get("page_title"):
                source.name = metadata["page_title"]

            source.extracted_text = extracted_text
            source.chunks_count = len(chunks)
            source.metadata_json = json.dumps(metadata)
            source.processing_status = ProcessingStatus.COMPLETED.value
            source.error_message = None
            db.commit()

            # Generate and persist chunks + vector embeddings
            KnowledgeService._generate_and_save_chunks(db, bot_id, source, chunks, metadata)

        except Exception as e:
            logger.error(f"Error scraping website {website_in.url}: {e}", exc_info=True)
            source.processing_status = ProcessingStatus.FAILED.value
            source.error_message = f"Failed to fetch website: {str(e)}"
            db.commit()

        db.refresh(source)
        return source

    @staticmethod
    def add_social_link(
        db: Session,
        bot_id: int,
        social_in: SocialLinkCreate,
        user_id: int
    ) -> KnowledgeSource:
        """
        Store and validate a social media URL for knowledge integration.
        """
        KnowledgeService.verify_bot_ownership(db, bot_id, user_id)

        # Detect platform from URL if not specified
        url_lower = social_in.url.lower()
        platform = social_in.platform or "Social Profile"
        if "linkedin.com" in url_lower:
            platform = "LinkedIn"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            platform = "X (Twitter)"
        elif "instagram.com" in url_lower:
            platform = "Instagram"
        elif "facebook.com" in url_lower:
            platform = "Facebook"
        elif "youtube.com" in url_lower:
            platform = "YouTube"
        elif "github.com" in url_lower:
            platform = "GitHub"

        display_name = social_in.name or f"{platform}: {social_in.url}"

        metadata = {
            "platform": platform,
            "url": social_in.url,
            "ready_for_crawling": True
        }

        extracted_text = f"Social Media Profile Link ({platform}): {social_in.url}"

        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=KnowledgeSourceType.SOCIAL_LINK.value,
            name=display_name,
            source_url=social_in.url,
            processing_status=ProcessingStatus.COMPLETED.value,
            extracted_text=extracted_text,
            chunks_count=1,
            metadata_json=json.dumps(metadata),
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        KnowledgeService._generate_and_save_chunks(db, bot_id, source, [extracted_text], metadata)
        db.refresh(source)
        return source

    @staticmethod
    def add_instructions(
        db: Session,
        bot_id: int,
        instr_in: InstructionCreate,
        user_id: int
    ) -> KnowledgeSource:
        """
        Add custom business instructions and objectives as a knowledge source.
        """
        KnowledgeService.verify_bot_ownership(db, bot_id, user_id)

        full_instruction_text = (
            f"PRIMARY INSTRUCTIONS:\n{instr_in.instructions}\n\n"
            f"RESPONSE TONE:\n{instr_in.tone or 'Friendly & professional'}\n\n"
        )
        if instr_in.restrictions:
            full_instruction_text += f"RESTRICTIONS & BOUNDARIES:\n{instr_in.restrictions}\n\n"
        if instr_in.objectives:
            full_instruction_text += f"CONVERSATION OBJECTIVES:\n{instr_in.objectives}\n\n"
        if instr_in.important_information:
            full_instruction_text += f"IMPORTANT BUSINESS FACTS:\n{instr_in.important_information}\n\n"

        metadata = {
            "tone": instr_in.tone,
            "has_restrictions": bool(instr_in.restrictions),
            "has_objectives": bool(instr_in.objectives),
            "character_count": len(full_instruction_text)
        }

        chunks = DocumentProcessor.chunk_text(full_instruction_text)

        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=KnowledgeSourceType.INSTRUCTION.value,
            name=instr_in.name,
            extracted_text=full_instruction_text,
            chunks_count=len(chunks),
            metadata_json=json.dumps(metadata),
            processing_status=ProcessingStatus.COMPLETED.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        KnowledgeService._generate_and_save_chunks(db, bot_id, source, chunks, metadata)
        db.refresh(source)
        return source

    @staticmethod
    def update_source(
        db: Session,
        source_id: int,
        source_in: KnowledgeSourceUpdate,
        user_id: int
    ) -> KnowledgeSource:
        """
        Update knowledge source details.
        """
        source = KnowledgeService.get_knowledge_source_by_id(db, source_id, user_id)

        if source_in.name is not None:
            source.name = source_in.name.strip()

        if source_in.instructions is not None and source.source_type == KnowledgeSourceType.INSTRUCTION.value:
            text = f"PRIMARY INSTRUCTIONS:\n{source_in.instructions}\n"
            if source_in.tone:
                text += f"\nTONE: {source_in.tone}\n"
            if source_in.restrictions:
                text += f"\nRESTRICTIONS: {source_in.restrictions}\n"
            if source_in.objectives:
                text += f"\nOBJECTIVES: {source_in.objectives}\n"
            source.extracted_text = text
            chunks = DocumentProcessor.chunk_text(text)
            source.chunks_count = len(chunks)
            db.commit()
            KnowledgeService._generate_and_save_chunks(db, source.bot_id, source, chunks, {})

        db.commit()
        db.refresh(source)
        return source

    @staticmethod
    def delete_source(db: Session, source_id: int, user_id: int) -> dict:
        """
        Delete a knowledge source and clean up any underlying file from disk.
        """
        source = KnowledgeService.get_knowledge_source_by_id(db, source_id, user_id)

        # Remove file from disk if it exists
        if source.file_path and os.path.exists(source.file_path):
            try:
                os.remove(source.file_path)
            except Exception as e:
                logger.warning(f"Could not remove file {source.file_path}: {e}")

        db.delete(source)
        db.commit()
        return {"message": "Knowledge source deleted successfully", "id": source_id}
