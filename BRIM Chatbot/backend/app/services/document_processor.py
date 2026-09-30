import re
import os
import json
import logging
from typing import Tuple, Dict, Any, List
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
import docx
from PIL import Image

logger = logging.getLogger(__name__)

class DocumentProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Normalize text, remove excess whitespace and non-printable characters.
        """
        if not text:
            return ""
        # Replace multiple newlines with at most 2 newlines
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Replace multiple spaces / tabs with single space
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
        """
        Split cleaned text into chunks with sliding window overlap for future embeddings.
        """
        cleaned = DocumentProcessor.clean_text(text)
        if not cleaned:
            return []
        if len(cleaned) <= chunk_size:
            return [cleaned]
        
        chunks = []
        start = 0
        while start < len(cleaned):
            end = min(start + chunk_size, len(cleaned))
            # Try to break at a paragraph or sentence boundary if possible
            if end < len(cleaned):
                last_period = cleaned.rfind('. ', start + chunk_size // 2, end)
                last_newline = cleaned.rfind('\n', start + chunk_size // 2, end)
                break_point = max(last_period, last_newline)
                if break_point != -1:
                    end = break_point + 1
            
            chunk = cleaned[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            if end >= len(cleaned):
                break
            start = end - overlap
            if start <= 0 or start >= len(cleaned):
                break
        return chunks

    @staticmethod
    def extract_from_pdf(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text and metadata from PDF files using pypdf.
        """
        reader = PdfReader(file_path)
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text)
        
        full_text = "\n\n".join(pages_text)
        metadata = {
            "page_count": len(reader.pages),
            "character_count": len(full_text),
            "parser": "pypdf"
        }
        return full_text, metadata

    @staticmethod
    def extract_from_docx(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from DOCX files using python-docx.
        """
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        # Also extract table text
        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    table_texts.append(row_text)
        
        full_text = "\n\n".join(paragraphs + table_texts)
        metadata = {
            "paragraph_count": len(paragraphs),
            "table_count": len(doc.tables),
            "character_count": len(full_text),
            "parser": "python-docx"
        }
        return full_text, metadata

    @staticmethod
    def extract_from_txt(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from raw text files with encoding fallbacks.
        """
        encodings = ["utf-8", "latin-1", "windows-1252"]
        content = ""
        used_enc = "utf-8"
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                used_enc = enc
                break
            except UnicodeDecodeError:
                continue
        
        metadata = {
            "encoding": used_enc,
            "character_count": len(content),
            "parser": "text-reader"
        }
        return content, metadata

    @staticmethod
    def extract_from_image(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Image extraction and metadata abstraction.
        Attempts OCR if pytesseract is available; otherwise records visual metadata.
        """
        with Image.open(file_path) as img:
            width, height = img.size
            format_name = img.format
            mode = img.mode

        ocr_text = ""
        ocr_status = "ocr_ready"
        
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(Image.open(file_path))
            ocr_status = "ocr_completed" if ocr_text.strip() else "ocr_no_text_found"
        except Exception as e:
            ocr_status = "ocr_engine_deferred"
            ocr_text = f"[Image Metadata: {format_name} {width}x{height} - Text extraction will run via vision OCR model in Phase 3]"

        metadata = {
            "width": width,
            "height": height,
            "format": format_name,
            "color_mode": mode,
            "ocr_status": ocr_status,
            "parser": "pillow-ocr"
        }
        return ocr_text, metadata

    @staticmethod
    def extract_from_website(url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Fetch website content, remove scripts/nav/ads, and extract clean text.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BRIM-AI-KnowledgeBot/1.0"
        }
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract title
        page_title = soup.title.string.strip() if soup.title and soup.title.string else url

        # Remove irrelevant elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside"]):
            element.decompose()

        # Extract textual content
        text = soup.get_text(separator="\n")
        cleaned_text = DocumentProcessor.clean_text(text)

        metadata = {
            "url": url,
            "page_title": page_title,
            "status_code": response.status_code,
            "character_count": len(cleaned_text),
            "parser": "beautifulsoup4"
        }
        return cleaned_text, metadata
