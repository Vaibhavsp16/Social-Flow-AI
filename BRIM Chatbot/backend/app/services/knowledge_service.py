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
from app.core.net_guard import UnsafeURLError, assert_safe_url
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
from app.core.industry_packs import BRIM_INDUSTRY_PACKS, get_pack
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.social_service import SocialService

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
    def _finalize_source(
        db: Session,
        source: KnowledgeSource,
        extracted_text: str,
        chunks: List[str],
        metadata: dict,
    ) -> None:
        """
        Persist extraction results and set an honest processing status.

        A source is only COMPLETED when it actually produced chunks. Otherwise it is marked
        FAILED with an actionable error, so the UI can show the real reason instead of
        silently reporting success over an empty knowledge base.
        """
        source.extracted_text = extracted_text
        source.chunks_count = len(chunks)
        source.metadata_json = json.dumps(metadata)
        if chunks:
            source.processing_status = ProcessingStatus.COMPLETED.value
            source.error_message = None
        else:
            source.processing_status = ProcessingStatus.FAILED.value
            if source.source_type == KnowledgeSourceType.IMAGE.value:
                source.error_message = (
                    "No text could be read from this image. Image ingestion needs an OCR "
                    "provider: set OPENAI_API_KEY, or install Tesseract and pytesseract. "
                    "Upload the text as a document in the meantime."
                )
            else:
                source.error_message = (
                    "No text could be extracted from this source, so no knowledge chunks were "
                    "created. Check that the content contains selectable text and try again."
                )
        db.commit()

    @staticmethod
    def _generate_and_save_chunks(
        db: Session,
        bot_id: int,
        source: KnowledgeSource,
        chunks: List[str],
        metadata: dict,
        chunk_pages: Optional[List[str]] = None,
    ):
        """
        Delete previous chunks for this source (if any) and insert newly embedded chunks.

        ``chunk_pages`` optionally carries the page URL each chunk came from, so citations
        point at the exact crawled page instead of only the seed URL.
        """
        db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).delete()

        for idx, chunk_text in enumerate(chunks):
            if not chunk_text or not chunk_text.strip():
                continue
            embedding, provider = EmbeddingService.get_embedding_with_provider(chunk_text)
            page_info = None
            if chunk_pages and idx < len(chunk_pages) and chunk_pages[idx]:
                page_info = chunk_pages[idx]
            elif source.source_type == KnowledgeSourceType.DOCUMENT.value and metadata.get("page_count"):
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
                embedding_vector=embedding,
                embedding_provider=provider,
            )
            db.add(chunk_record)
        db.flush()

        from app.models.activity import ActivityType
        from app.services.activity_service import log_activity

        log_activity(
            db, ActivityType.KNOWLEDGE_ADDED.value,
            user_id=getattr(getattr(source.bot, "project", None), "user_id", None),
            entity_type="knowledge_source", entity_id=source.id,
            metadata={"source_type": source.source_type, "chunks": len(chunks)},
        )
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

        # Re-uploading the same file used to add a second identical source, which then produced
        # the same passage twice in retrieval and doubled every citation. Replace it instead.
        duplicates = (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.bot_id == bot_id,
                KnowledgeSource.original_filename == filename,
                KnowledgeSource.file_size == file_size,
            )
            .all()
        )
        for duplicate in duplicates:
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.knowledge_source_id == duplicate.id
            ).delete()
            old_path = duplicate.file_path
            db.delete(duplicate)
            db.commit()
            if old_path and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

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
            elif file_ext in {".dxf", ".dwg"}:
                extracted_text, metadata = DocumentProcessor.extract_from_cad(str(storage_path))

            chunks = DocumentProcessor.chunk_text(extracted_text)

            KnowledgeService._finalize_source(db, source, extracted_text, chunks, metadata)

            # Generate and persist chunks + vector embeddings
            # OCR'd PDFs carry "Page N" markers in the text; keep them as the citation label
            # so a reader can open the brochure at the right page.
            # Any PDF carries "Page N" markers now, whether the text came from the text layer or
            # from OCR, so the citation always names the page a reader can open.
            chunk_pages = (
                DocumentProcessor.page_labels(chunks)
                if metadata.get("page_markers") or metadata.get("ocr")
                else None
            )
            KnowledgeService._generate_and_save_chunks(
                db, bot_id, source, chunks, metadata, chunk_pages
            )

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

        # Validate before creating a source row: an internal URL should be rejected outright,
        # not stored as a failed ingest attempt.
        try:
            assert_safe_url(website_in.url)
        except UnsafeURLError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

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
            extracted_text, metadata = DocumentProcessor.crawl_website(
                website_in.url, max_pages=getattr(website_in, "max_pages", 1) or 1
            )

            # Chunk page by page so every chunk keeps the URL it came from, even in a
            # multi-page crawl. Page text itself stays out of the stored metadata.
            pages = metadata.get("pages") or [{"url": website_in.url, "text": extracted_text}]
            chunks: List[str] = []
            chunk_pages: List[str] = []
            for page in pages:
                for chunk in DocumentProcessor.chunk_text(page.get("text", "")):
                    chunks.append(chunk)
                    chunk_pages.append(page.get("url") or website_in.url)
            metadata["pages"] = [
                {k: v for k, v in page.items() if k != "text"} for page in pages
            ]

            if not website_in.name and metadata.get("page_title"):
                source.name = metadata["page_title"]

            KnowledgeService._finalize_source(db, source, extracted_text, chunks, metadata)

            # Generate and persist chunks + vector embeddings
            KnowledgeService._generate_and_save_chunks(
                db, bot_id, source, chunks, metadata, chunk_pages=chunk_pages
            )

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

        try:
            assert_safe_url(social_in.url)
        except UnsafeURLError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        extracted_text, metadata = SocialService.ingest(
            social_in.url,
            platform=social_in.platform,
            caption=getattr(social_in, "caption", None),
            name=social_in.name,
        )
        platform = metadata.get("platform") or "Social Profile"
        display_name = social_in.name or f"{platform}: {social_in.url}"

        chunks = DocumentProcessor.chunk_text(extracted_text) or [extracted_text]
        chunk_pages = [f"Profile: {platform}"] * len(chunks)

        # Re-adding a link (for example after correcting the caption) replaces the old entry
        # rather than leaving two profiles that answer the same question differently.
        for duplicate in (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.bot_id == bot_id,
                KnowledgeSource.source_type == KnowledgeSourceType.SOCIAL_LINK.value,
                KnowledgeSource.source_url == social_in.url,
            )
            .all()
        ):
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.knowledge_source_id == duplicate.id
            ).delete()
            db.delete(duplicate)
            db.commit()

        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=KnowledgeSourceType.SOCIAL_LINK.value,
            name=display_name,
            source_url=social_in.url,
            processing_status=ProcessingStatus.PROCESSING.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        KnowledgeService._finalize_source(db, source, extracted_text, chunks, metadata)
        KnowledgeService._generate_and_save_chunks(
            db, bot_id, source, chunks, metadata, chunk_pages=chunk_pages
        )
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
            processing_status=ProcessingStatus.PROCESSING.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        KnowledgeService._finalize_source(db, source, full_instruction_text, chunks, metadata)
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

    # ── BRIM industry knowledge packs ─────────────────────────────────────────

    @staticmethod
    def get_industry_packs() -> List[dict]:
        """The eight BRIM industries and the knowledge pack available for each."""
        return BRIM_INDUSTRY_PACKS

    @staticmethod
    def _industry_pack_dir() -> Path:
        """Locate demo_documents/brim from the working directory or the package root."""
        local = Path("demo_documents") / "brim"
        if local.is_dir():
            return local
        return Path(__file__).resolve().parent.parent.parent / "demo_documents" / "brim"

    @staticmethod
    def seed_industry_pack(db: Session, bot_id: int, industry_key: str, user_id: int) -> KnowledgeSource:
        """
        Attach the BRIM knowledge pack for one industry to a bot.

        Re-seeding the same industry refreshes the existing source instead of adding a
        duplicate, which keeps the knowledge list clean during demos.
        """
        KnowledgeService.verify_bot_ownership(db, bot_id, user_id)

        pack = get_pack(industry_key)
        if not pack:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown industry pack '{industry_key}'.",
            )

        pack_path = KnowledgeService._industry_pack_dir() / pack["filename"]
        if not pack_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Industry pack file '{pack['filename']}' is missing on the server. "
                    "Run scripts/build_industry_packs.py to rebuild it."
                ),
            )
        content = pack_path.read_text(encoding="utf-8").strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Industry pack file is empty.",
            )

        # Replace a previous copy of the same pack for this bot.
        for existing in (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.bot_id == bot_id,
                KnowledgeSource.source_type == KnowledgeSourceType.DOCUMENT.value,
                KnowledgeSource.name == pack["name"],
            )
            .all()
        ):
            db.delete(existing)
            db.commit()

        metadata = {
            "is_industry_pack": True,
            "industry": pack["industry"],
            "pack_key": pack["key"],
            "source_url": pack["url"],
            "character_count": len(content),
        }

        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=KnowledgeSourceType.DOCUMENT.value,
            name=pack["name"],
            source_url=pack["url"],
            original_filename=pack["filename"],
            file_size=len(content.encode("utf-8")),
            processing_status=ProcessingStatus.PROCESSING.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        chunks = DocumentProcessor.chunk_text(content)
        KnowledgeService._finalize_source(db, source, content, chunks, metadata)
        KnowledgeService._generate_and_save_chunks(db, bot_id, source, chunks, metadata)
        db.refresh(source)
        return source

    SAMPLE_DOCS = {
        "real_estate": {
            "key": "real_estate",
            "name": "Prycoons Real Estate Official Guide",
            "filename": "Prycoons_Real_Estate_Guide.txt",
            "industry": "Real Estate",
            "description": "Comprehensive pricing, amenities, and floor plans for Sunset Palms & The Heights in Ambli.",
        },
        "healthcare": {
            "key": "healthcare",
            "name": "Apex Healthcare Wellness Clinic Guide",
            "filename": "Apex_Healthcare_Clinic_Guide.txt",
            "industry": "Healthcare",
            "description": "Doctors, specialist timings, consultation charges, emergency line, and accepted insurances.",
        },
        "saas": {
            "key": "saas",
            "name": "CloudScale SaaS Platform Documentation",
            "filename": "CloudScale_SaaS_Platform_Docs.txt",
            "industry": "Technology & SaaS",
            "description": "Pricing tiers ($49, $199, Enterprise), API rate limits, SSO, SOC 2 compliance, and SLA.",
        },
    }

    @staticmethod
    def get_sample_documents() -> list:
        return list(KnowledgeService.SAMPLE_DOCS.values())

    @staticmethod
    def seed_sample_document(db: Session, bot_id: int, sample_key: str, user_id: int) -> KnowledgeSource:
        bot = KnowledgeService.verify_bot_ownership(db, bot_id, user_id)
        sample = KnowledgeService.SAMPLE_DOCS.get(sample_key)
        if not sample:
            sample = KnowledgeService.SAMPLE_DOCS["real_estate"]

        doc_path = Path("demo_documents") / sample["filename"]
        if not doc_path.exists():
            doc_path = Path(__file__).resolve().parent.parent.parent / "demo_documents" / sample["filename"]

        content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
        if not content:
            raise HTTPException(status_code=500, detail="Demo document template not found on server.")

        source = KnowledgeSource(
            bot_id=bot_id,
            source_type=KnowledgeSourceType.DOCUMENT.value,
            name=sample["name"],
            original_filename=sample["filename"],
            file_size=len(content.encode("utf-8")),
            processing_status=ProcessingStatus.PROCESSING.value,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        chunks = DocumentProcessor.chunk_text(content)
        metadata = {
            "is_demo_sample": True,
            "industry": sample["industry"],
            "character_count": len(content),
            "chunk_count": len(chunks),
        }

        KnowledgeService._finalize_source(db, source, content, chunks, metadata)
        KnowledgeService._generate_and_save_chunks(db, bot_id, source, chunks, metadata)
        db.refresh(source)
        return source
