import re
import os
import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
import docx
from PIL import Image

from app.core.net_guard import UnsafeURLError, assert_safe_url

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
        text = DocumentProcessor._repair_line_wraps(text)
        return text.strip()

    # A PDF exported from a browser or a DTP tool often lays out every single word on its own
    # line ("Prycoons" / "-" / "The" / "Name" / "Of" / "Game"). Chunked verbatim that becomes
    # useless for both embeddings and keyword matching, so word-per-line text is reflowed into
    # real sentences before it reaches the chunker.
    WORD_PER_LINE_RATIO = 0.35

    @staticmethod
    def _repair_line_wraps(text: str) -> str:
        if not text:
            return text
        lines = [line.strip() for line in text.split("\n")]
        words = [line for line in lines if line]
        if len(words) < 4:
            return text
        single_word = sum(1 for line in words if len(line.split()) == 1)
        if single_word / len(words) < DocumentProcessor.WORD_PER_LINE_RATIO:
            return text

        reflowed: List[str] = []
        buffer: List[str] = []
        for line in lines:
            if not line:
                continue
            buffer.append(line)
            joined = " ".join(buffer)
            if line.endswith((".", "!", "?", ":", ";")) or len(joined) >= 160:
                reflowed.append(joined)
                buffer = []
        if buffer:
            reflowed.append(" ".join(buffer))
        return "\n".join(reflowed)

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
        Extract text from a PDF page by page, transcribing pages that only contain images.

        Three document shapes have to work: an ordinary text PDF, a scanned or brochure PDF whose
        pages are single images, and a mixed PDF where the text pages extract cleanly but the
        floor-plan pages are drawings. Deciding once for the whole file lost the drawings, which
        is exactly where pricing and area information sits, so the decision is per page.
        """
        reader = PdfReader(file_path)
        page_count = len(reader.pages)

        document = None
        try:
            import pymupdf

            document = pymupdf.open(file_path)
        except Exception as exc:  # noqa: BLE001
            logger.info("PDF page rendering unavailable, text layer only: %s", exc)

        sections: List[str] = []
        ocred_pages = 0
        skipped_pages: List[int] = []
        try:
            for index, page in enumerate(reader.pages):
                try:
                    page_text = DocumentProcessor.clean_text(page.extract_text() or "")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pypdf failed on page %s: %s", index + 1, exc)
                    page_text = ""

                if len(page_text) < DocumentProcessor.PAGE_TEXT_MIN_CHARS and document is not None:
                    if ocred_pages < DocumentProcessor.MAX_OCR_PAGES:
                        ocr_text = DocumentProcessor._ocr_rendered_page(document, index)
                        if ocr_text:
                            ocred_pages += 1
                            page_text = DocumentProcessor._merge_page_text(page_text, ocr_text)
                    else:
                        skipped_pages.append(index + 1)

                if page_text.strip():
                    # Always mark the page so citations point at a real page number, whatever
                    # produced the text.
                    sections.append(f"Page {index + 1}\n{page_text.strip()}")
        finally:
            if document is not None:
                try:
                    document.close()
                except Exception:  # noqa: BLE001
                    pass

        full_text = "\n\n".join(sections)
        metadata = {
            "page_count": page_count,
            "character_count": len(full_text),
            "parser": "pypdf+vision" if ocred_pages else "pypdf",
            "ocr": ocred_pages > 0,
            "pages_ocred": ocred_pages,
            "page_markers": True,
        }
        if skipped_pages:
            metadata["ocr_skipped_pages"] = skipped_pages
        return full_text, metadata

    PAGE_MARKER_LINE = re.compile(r"(?i)^page\s*\d+$")

    @staticmethod
    def _merge_page_text(extracted: str, ocr_text: str) -> str:
        """
        Combine the text layer with the transcript without duplicating either.

        A drawing page has a short title block plus an image, so it is transcribed; the
        transcript then repeats the title block. Comparing whole lines missed that because OCR
        spacing differs, so a line is dropped when most of its words already appear.
        """
        if not extracted:
            return ocr_text
        if not ocr_text:
            return extracted
        known_words = set(re.findall(r"[A-Za-z0-9]{3,}", extracted.lower()))
        extra: List[str] = []
        for line in ocr_text.splitlines():
            candidate = line.strip()
            if not candidate or DocumentProcessor.PAGE_MARKER_LINE.match(candidate):
                continue
            words = re.findall(r"[A-Za-z0-9]{3,}", candidate.lower())
            if words and sum(word in known_words for word in words) / len(words) >= 0.6:
                continue
            extra.append(candidate)
        return extracted + ("\n" + "\n".join(extra) if extra else "")

    @staticmethod
    def page_labels(chunks: List[str]) -> List[str]:
        """
        Page label per chunk for OCR'd PDFs.

        The transcript is prefixed with "Page N" markers, but a chunk boundary can fall before
        the next marker. Carry the last seen page forward so every chunk still cites a page.
        """
        labels: List[str] = []
        current = None
        for chunk in chunks:
            match = re.search(r"\bPage (\d+)\b", chunk)
            if match:
                current = f"Page {match.group(1)}"
            labels.append(current or "Page 1")
        return labels

    @staticmethod
    def _ocr_rendered_page(document, index: int) -> str:
        """Render one page of an open PyMuPDF document and transcribe it."""
        image_path = os.path.join(tempfile.gettempdir(), f"brim_pdf_{uuid.uuid4().hex}.png")
        try:
            document[index].get_pixmap(dpi=DocumentProcessor.OCR_RENDER_DPI).save(image_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not render PDF page %s: %s", index + 1, exc)
            return ""
        try:
            transcript = DocumentProcessor._vision_ocr(image_path)
        finally:
            try:
                os.remove(image_path)
            except OSError:
                pass
        # The page number is printed on the page itself; the caller adds the label.
        return "\n".join(
            line for line in transcript.splitlines()
            if not DocumentProcessor.PAGE_MARKER_LINE.match(line.strip())
        ).strip()

    @staticmethod
    def extract_from_docx(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from DOCX in reading order, including tables and embedded images.

        Paragraphs and tables used to be collected into two separate lists, which moved every
        table to the end of the document and broke the surrounding headings away from their
        values. Body order is preserved here, and images pasted into a Word file (site maps,
        floor plans, screenshots) are transcribed rather than dropped.
        """
        doc = docx.Document(file_path)
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        blocks: List[str] = []
        paragraph_count = 0
        table_count = 0
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                paragraph = Paragraph(child, doc)
                text = paragraph.text.strip()
                if not text:
                    continue
                style = (paragraph.style.name or "").lower()
                # Keep section headings recognisable to the retriever; a heading glued to the
                # next paragraph loses the "what is this about" signal.
                if ("heading" in style or "title" in style) and not text.endswith(
                    (".", "!", "?", ":", ";")
                ):
                    text = f"{text}:"
                blocks.append(text)
                paragraph_count += 1
            elif tag == "tbl":
                table_count += 1
                table = Table(child, doc)
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        blocks.append(" | ".join(cells))

        for section in doc.sections:
            for header_footer in (section.header, section.footer):
                try:
                    text = " ".join(p.text.strip() for p in header_footer.paragraphs if p.text.strip())
                except Exception:  # noqa: BLE001
                    text = ""
                if text:
                    blocks.append(text)

        image_texts = DocumentProcessor._ocr_docx_images(doc)
        blocks.extend(image_texts)

        full_text = "\n\n".join(blocks)
        metadata = {
            "paragraph_count": paragraph_count,
            "table_count": table_count,
            "images_ocred": len(image_texts),
            "character_count": len(full_text),
            "parser": "python-docx",
        }
        return full_text, metadata

    @staticmethod
    def _ocr_docx_images(doc, max_images: int = 12) -> List[str]:
        """Transcribe images embedded in a Word document (plans, site maps, screenshots)."""
        texts: List[str] = []
        try:
            relationships = doc.part.rels
        except Exception:  # noqa: BLE001
            return texts

        index = 0
        for rel in relationships.values():
            if index >= max_images:
                break
            if "image" not in getattr(rel, "reltype", ""):
                continue
            try:
                blob = rel.target_part.blob
            except Exception:  # noqa: BLE001
                continue
            # Icons and bullets are small in pixel terms; diagrams and plans are not. Size in
            # bytes is a poor test because a mostly-white PNG compresses to a few kilobytes.
            if len(blob) < DocumentProcessor.DOCX_IMAGE_MIN_BYTES:
                continue
            path = os.path.join(tempfile.gettempdir(), f"brim_docx_{uuid.uuid4().hex}.png")
            try:
                with open(path, "wb") as handle:
                    handle.write(blob)
                try:
                    with Image.open(path) as probe:
                        if probe.width * probe.height < DocumentProcessor.DOCX_IMAGE_MIN_PIXELS:
                            continue
                except Exception:  # noqa: BLE001
                    continue
                text = DocumentProcessor._vision_ocr(path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("DOCX image OCR failed: %s", exc)
                text = ""
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            if text.strip():
                index += 1
                texts.append(f"Image {index} (text transcribed from an embedded image)\n{text.strip()}")
        return texts

    @staticmethod
    def extract_from_cad(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Text from CAD drawings.

        DXF is parsed properly with ezdxf (TEXT / MTEXT / ATTRIB / DIMENSION plus layer and block
        names). DWG is a closed binary format; without an ODA converter we salvage printable
        ASCII runs, which usually recovers room and area labels. Both return text the chunker can
        index, so a plan drawing can answer "what is the carpet area on the typical floor?".
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".dxf":
            try:
                import ezdxf

                doc = ezdxf.readfile(str(path))
                lines: List[str] = []

                for entity in doc.modelspace():
                    kind = entity.dxftype()
                    if kind == "TEXT":
                        lines.append(entity.dxf.text)
                    elif kind == "MTEXT":
                        lines.append(entity.plain_text() or entity.text)
                    elif kind in {"ATTRIB", "ATTDEF"}:
                        lines.append(f"{entity.dxf.tag}: {entity.dxf.text}")
                    elif kind == "DIMENSION":
                        text = getattr(entity.dxf, "text", "") or ""
                        if text and text not in ("<>", ""):
                            lines.append(text)

                layers = sorted({layer.dxf.name for layer in doc.layers})
                blocks = sorted({block.name for block in doc.blocks if not block.name.startswith("*")})
                if layers:
                    lines.append("Layers: " + ", ".join(layers[:60]))
                if blocks:
                    lines.append("Blocks: " + ", ".join(blocks[:60]))

                text = "\n".join(line for line in lines if str(line).strip())
                return text, {
                    "parser": "ezdxf",
                    "cad_format": "DXF",
                    "entities": len(list(doc.modelspace())),
                    "character_count": len(text),
                }
            except ImportError:
                return "", {"parser": "none", "error": "ezdxf not installed"}
            except Exception as exc:  # noqa: BLE001
                return "", {"parser": "ezdxf", "error": str(exc)[:200]}

        # DWG is a closed binary format. Conversion via an ODA File Converter (or the LibreDWG
        # `dwg2dxf` tool) gives a faithful DXF, so use it when one is installed and fall back to
        # reading the strings out of the binary otherwise.
        converted = DocumentProcessor._convert_dwg_to_dxf(path)
        if converted is not None:
            text, metadata = DocumentProcessor.extract_from_cad(str(converted))
            metadata["cad_format"] = "DWG"
            metadata["parser"] = f"{metadata.get('parser')}+converted"
            metadata["converted_from"] = "DWG"
            try:
                converted.unlink()
            except OSError:
                pass
            if text.strip():
                return text, metadata

        try:
            raw = path.read_bytes()
        except OSError as exc:
            return "", {"parser": "dwg-scan", "error": str(exc)}

        seen: set = set()
        lines: List[str] = []

        # DWG R2007 and later store text as UTF-16LE, so plain ASCII scanning misses most labels.
        for match in re.finditer(rb"(?:[\x20-\x7E]\x00){4,}", raw):
            try:
                candidate = match.group().decode("utf-16-le", "ignore").strip()
            except Exception:  # noqa: BLE001
                continue
            DocumentProcessor._collect_cad_line(candidate, seen, lines)

        for run in re.findall(rb"[\x20-\x7E]{4,}", raw):
            DocumentProcessor._collect_cad_line(run.decode("ascii", "ignore"), seen, lines)

        text = "\n".join(lines[:1000])
        return text, {
            "parser": "dwg-scan",
            "cad_format": "DWG",
            "character_count": len(text),
            "note": (
                "DWG text was recovered from the binary. Install the ODA File Converter (or "
                "LibreDWG) for full fidelity, or upload the DXF export."
            ),
        }

    CAD_NOISE = re.compile(
        r"(acad|autodesk|objectdbx|dwg|\.dll|\.arx|\.ctb|\.stb|\.shx|\.ttf|"
        r"^[A-Za-z]{2,}Version|^\$[A-Z]+|^,[0-9]|^[0-9.]+$)",
        re.IGNORECASE,
    )

    @staticmethod
    def _collect_cad_line(candidate: str, seen: set, lines: List[str]) -> None:
        """Keep a printable CAD string if it looks like a label rather than format noise."""
        text = candidate.replace("\\P", " ").strip(" \x00")
        low = text.lower()
        if len(text) < 4 or low in seen:
            return
        if not re.search(r"[a-z]{2,}", low):
            return
        if DocumentProcessor.CAD_NOISE.search(text):
            return
        seen.add(low)
        lines.append(text)

    @staticmethod
    def _convert_dwg_to_dxf(path: Path) -> Optional[Path]:
        """
        Convert DWG to DXF with an external converter, if one is configured or on PATH.

        Optional by design: the app keeps working without it, and the binary scan below still
        recovers most drawing labels.
        """
        import shutil
        import subprocess

        out_dir = Path(tempfile.gettempdir()) / f"brim_cad_{uuid.uuid4().hex}"
        out_dir.mkdir(parents=True, exist_ok=True)

        odaconverter = os.getenv("ODA_CONVERTER_PATH") or shutil.which("ODAFileConverter")
        dwg2dxf = shutil.which("dwg2dxf")

        try:
            if odaconverter:
                subprocess.run(
                    [
                        odaconverter, str(path.parent), str(out_dir), "ACAD2018", "DXF",
                        "0", "1", path.name,
                    ],
                    check=True, capture_output=True, timeout=120,
                )
            elif dwg2dxf:
                subprocess.run(
                    [dwg2dxf, "-o", str(out_dir / (path.stem + ".dxf")), str(path)],
                    check=True, capture_output=True, timeout=120,
                )
            else:
                shutil.rmtree(out_dir, ignore_errors=True)
                return None
        except Exception as exc:  # noqa: BLE001
            logger.info("DWG conversion unavailable (%s); scanning the binary", exc)
            shutil.rmtree(out_dir, ignore_errors=True)
            return None

        produced = list(out_dir.glob("*.dxf")) or list(out_dir.glob("*.DXF"))
        if not produced:
            shutil.rmtree(out_dir, ignore_errors=True)
            return None
        return produced[0]

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
        except Exception:
            # No local OCR engine (pytesseract and the tesseract binary are optional). Fall back
            # to the vision model so an image still becomes searchable knowledge instead of a
            # metadata placeholder that can only ever produce refusals.
            vision_text = DocumentProcessor._vision_ocr(file_path)
            if vision_text:
                ocr_text = vision_text
                ocr_status = "ocr_completed_vision"
            else:
                ocr_status = "ocr_unavailable"
                ocr_text = ""

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
    def _vision_ocr(file_path: str, prompt: Optional[str] = None) -> str:
        """Transcribe an image with the vision model. Returns "" when unavailable."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ""
        try:
            import base64
            import mimetypes

            from openai import OpenAI

            mime = mimetypes.guess_type(file_path)[0] or "image/png"
            with open(file_path, "rb") as handle:
                encoded = base64.b64encode(handle.read()).decode("ascii")

            instruction = prompt or (
                "Transcribe every readable word from this page exactly, keeping the reading "
                "order and line breaks. Include headings, table cells, labels, dimensions, "
                "areas, prices and footnotes. Do not summarise and do not add commentary. "
                "Output only the transcribed text. If there is no readable text, output nothing."
            )

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{encoded}",
                                # Small type on drawings is unreadable at low detail.
                                "detail": "high",
                            },
                        },
                    ],
                }],
                temperature=0,
                max_tokens=2000,
            )
            text = (response.choices[0].message.content or "").strip()
            # The model sometimes wraps the transcript in a fenced block; that is markup, not
            # page content, and it pollutes chunks.
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return text.strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Vision OCR failed: {exc}")
            return ""

    # ── Website crawling ──────────────────────────────────────────────────────

    REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 BRIM-AI-KnowledgeBot/1.0"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Structural chrome that never carries knowledge. Removed before text extraction so the
    # bot does not learn navigation labels, cookie banners or contact-form placeholders.
    NOISE_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside"]

    # Theme/plugin chrome that is markup-level noise on CMS sites (Avada/Elementor/WordPress in
    # particular). Matched as whole class tokens, not substrings: a substring match on
    # "rev-slider" also hits utility classes like "avada-has-rev-slider-styles" and would delete
    # the page content along with the chrome.
    NOISE_CLASS_TOKENS = {
        "navbar", "mainmenu", "menu-item", "mobile-menu", "breadcrumb", "breadcrumbs",
        "cookie", "cookie-bar", "gdpr", "newsletter", "popup", "popover", "modal",
        "sidebar", "search-form", "social-icons", "share-box", "related-posts",
        "comments-area", "slidingbar-area", "widget", "menu",
    }
    NOISE_CLASS_PREFIXES = (
        "fusion-menu", "fusion-sliding-bar", "fusion-secondary-menu",
        "awb-off-canvas", "elementor-popup",
    )

    # Meta fields worth keeping when the visible body is thin (JS-rendered sites).
    STRUCTURED_META_NAMES = {
        "description", "og:description", "og:title", "og:site_name", "twitter:description",
    }

    # Non-HTML resources that must never be queued as crawl targets.
    SKIP_LINK_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".pdf", ".zip", ".rar",
        ".mp4", ".mp3", ".mov", ".css", ".js", ".xml", ".json", ".woff", ".woff2", ".ttf",
    }

    # A business site is usually 10-40 real pages. Twelve was too low to reach product or about
    # pages on a shop, so the crawl stopped at whatever the homepage linked to.
    MAX_CRAWL_PAGES = 40
    # Deep enough to reach a sitemap child's children, shallow enough to stay topical.
    MAX_CRAWL_DEPTH = 2
    # Wall-clock ceiling for one ingest. Without it, 40 slow pages at a 20s timeout each could hold
    # a request open for ten minutes.
    CRAWL_TIME_BUDGET_SECONDS = 75
    # Total extracted text ceiling. Beyond this the extra pages add cost to every question without
    # adding answers.
    MAX_CRAWL_CHARS = 400_000
    # Paths that are chrome, commerce plumbing or duplicates rather than knowledge.
    CRAWL_SKIP_PATHS = (
        "/login", "/signin", "/sign-in", "/register", "/my-account", "/account", "/wishlist",
        "/compare", "/cart", "/checkout", "/privacy", "/terms", "/refund",
        "/shipping-policy", "/cookie", "/search", "/404", "/sitemap",
    )
    # Below this many characters a page is treated as unreadable rather than as knowledge.
    MIN_CRAWL_CHARS = 120
    # A PDF page with less selectable text than this is treated as image-led and transcribed.
    # Plan layouts are the case that matters: the title block gives a few dozen characters, the
    # drawing holds the areas and dimensions.
    PAGE_TEXT_MIN_CHARS = 400
    # Ceiling on vision calls per document so a 200-page catalogue cannot run up a bill.
    MAX_OCR_PAGES = 20
    # 150 DPI lost the small dimension text on floor plans; 200 DPI reads it.
    OCR_RENDER_DPI = 200
    # Images smaller than these in a Word file are icons and bullets, not diagrams.
    DOCX_IMAGE_MIN_BYTES = 4_000
    DOCX_IMAGE_MIN_PIXELS = 120_000

    @staticmethod
    def _fetch_html(client: httpx.Client, url: str) -> Tuple[str, int, str]:
        """Fetch a URL and return (html, status_code, final_url). Raises on HTTP errors."""
        current = assert_safe_url(url)
        response = None
        for _hop in range(5):
            response = client.get(current, headers=DocumentProcessor.REQUEST_HEADERS)
            if response.is_redirect and response.headers.get("location"):
                current = assert_safe_url(urljoin(current, response.headers["location"]))
                continue
            break
        else:
            raise ValueError("Too many redirects while fetching the URL.")

        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise ValueError(f"Unsupported content type '{content_type}' at {url}")
        return response.text, response.status_code, str(response.url)

    @staticmethod
    def _normalise_url(url: str) -> Optional[str]:
        """Absolute http(s) URL without fragment or trailing slash, or None when not crawlable."""
        try:
            parsed = urlparse(url.strip())
        except ValueError:
            return None
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))

    @classmethod
    def _is_crawlable(cls, link: str, base: Any) -> bool:
        """Same-site HTML page that is worth crawling (no assets, admin, feeds or anchors)."""
        if not link or link.startswith(("mailto:", "tel:", "javascript:", "#")):
            return False
        parsed = urlparse(link)
        if parsed.scheme not in ("http", "https"):
            return False
        # Treat www. and the apex domain as the same site. Many hosts redirect the apex to www,
        # and a strict netloc comparison then rejected every link on the page.
        if cls._bare_host(parsed.netloc) != cls._bare_host(base.netloc):
            return False
        lowered = parsed.path.lower()
        if any(lowered.endswith(ext) for ext in cls.SKIP_LINK_EXTENSIONS):
            return False
        blocked = (
            "/wp-admin", "/wp-login", "/feed", "/cart", "/checkout", "/author/", "/tag/",
            "/cdn-cgi/",  # Cloudflare bot-challenge endpoints serve unrelated decoy HTML
        )
        if any(part in lowered for part in blocked):
            return False
        if parsed.query and "replytocom" in parsed.query:
            return False
        return True

    @staticmethod
    def _is_descendant(link: str, base: Any) -> bool:
        """
        True when the link sits under the seed path, or anywhere on the site when the seed is
        the root. Sibling sections are excluded so a focused page stays focused.
        """
        path = urlparse(link).path or "/"
        seed_path = base.path or "/"
        if seed_path in ("", "/"):
            return True

        if seed_path.endswith("/"):
            # Directory seed: everything beneath it is in scope.
            scope = seed_path
        elif "." in seed_path.rsplit("/", 1)[-1]:
            # File seed such as /index.html or /guide.pdf: its own directory is the scope.
            scope = seed_path.rsplit("/", 1)[0] + "/"
        else:
            # Extensionless page such as /services: treat it as a section root.
            scope = seed_path + "/"

        return path.startswith(scope) and path.rstrip("/") != seed_path.rstrip("/")

    @staticmethod
    def _bare_host(netloc: str) -> str:
        host = (netloc or "").lower().split(":")[0]
        return host[4:] if host.startswith("www.") else host

    @classmethod
    def _meta_and_jsonld(cls, soup: "BeautifulSoup") -> str:
        """
        Text that survives on JavaScript-heavy sites: meta descriptions and structured data.

        A shop built on a JS framework renders its copy client-side, so the HTML body holds almost
        nothing while the meta description and JSON-LD carry the product and business facts. Reading
        those turned a 191-character page into usable knowledge.
        """
        parts: List[str] = []
        for tag in soup.find_all("meta"):
            name = (tag.get("name") or tag.get("property") or "").lower()
            if name in cls.STRUCTURED_META_NAMES:
                content = (tag.get("content") or "").strip()
                if len(content) > 3:
                    parts.append(content)

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except Exception:  # noqa: BLE001 - malformed structured data is common
                continue
            stack = [data]
            while stack and len(parts) < 120:
                node = stack.pop()
                if isinstance(node, dict):
                    stack.extend(node.values())
                elif isinstance(node, list):
                    stack.extend(node)
                elif isinstance(node, str):
                    value = re.sub(r"\s+", " ", node).strip()
                    if 3 < len(value) < 600 and value not in parts:
                        parts.append(value)

        # Dedupe while keeping order.
        deduped, seen = [], set()
        for part in parts:
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(part)
        return "\n".join(deduped)[:6000]

    @classmethod
    def _is_junk_path(cls, link: str) -> bool:
        """Account, checkout, policy and search pages: chrome, not knowledge."""
        path = urlparse(link).path.lower().rstrip("/") or "/"
        if any(path == junk or path.startswith(junk + "/") for junk in cls.CRAWL_SKIP_PATHS):
            return True
        # Policy pages carry suffixes ("/privacy-policy", "/terms-of-service"). Prefix matching is
        # limited to these because a prefix on "/cart" would also swallow "/cartoon".
        return any(path.startswith(prefix) for prefix in ("/privacy", "/terms", "/refund", "/cookie"))

    @classmethod
    def _rank_links(cls, links: List[str], base: Any) -> List[str]:
        """
        Same-host content links, the seed's own section first.

        Ranking rather than filtering: a shop's homepage links to /about and /products, which are
        siblings of /, and the old descendant test rejected both.
        """
        ordered: List[str] = []
        seen = set()
        ranked = []
        for link in links:
            if not cls._is_crawlable(link, base) or cls._is_junk_path(link):
                continue
            normalised = cls._normalise_url(link)
            if not normalised or normalised in seen:
                continue
            seen.add(normalised)
            # Descendants of the seed path are the most topical, so they go first.
            ranked.append((0 if cls._is_descendant(link, base) else 1, normalised))
        for _, link in sorted(ranked, key=lambda pair: pair[0]):
            ordered.append(link)
        return ordered[:20]

    @classmethod
    def _sitemap_urls(cls, client: httpx.Client, base: Any) -> List[str]:
        """
        Page URLs from the site's sitemap, best effort.

        A sitemap is the only reliable way to find pages that the homepage does not link to, which
        is common on catalogue and CMS sites. Any failure here is non-fatal: the link walk still
        runs.
        """
        found: List[str] = []
        candidates = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]
        try:
            for path in candidates:
                if len(found) >= 60:
                    break
                url = urljoin(f"{base.scheme}://{base.netloc}", path)
                try:
                    response = client.get(assert_safe_url(url), headers=cls.REQUEST_HEADERS)
                except Exception:
                    continue
                if response.status_code != 200 or "<" not in response.text[:200]:
                    continue

                locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", response.text, flags=re.I)
                if not locs:
                    continue

                if "<sitemapindex" in response.text[:1000]:
                    # Index of sitemaps: read the first few children, not all of them.
                    for child in locs[:3]:
                        try:
                            sub = client.get(assert_safe_url(child), headers=cls.REQUEST_HEADERS)
                            if sub.status_code == 200:
                                locs.extend(
                                    re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sub.text, flags=re.I)
                                )
                        except Exception:
                            continue

                for loc in locs:
                    if "sitemap" in loc.lower():
                        continue
                    if not cls._is_crawlable(loc, base) or cls._is_junk_path(loc):
                        continue
                    normalised = cls._normalise_url(loc)
                    if normalised and normalised not in found:
                        found.append(normalised)
                    if len(found) >= 60:
                        break
                if found:
                    break
        except Exception as exc:  # noqa: BLE001
            logger.info("Sitemap discovery skipped: %s", exc)
        return found

    # Publish timestamps and click labels are interface, not knowledge.
    NOISE_LINE_PATTERNS = (
        re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"),
        re.compile(r"^(?:read|view|learn|see) more$", re.IGNORECASE),
    )

    @classmethod
    def _is_noise_line(cls, line: str) -> bool:
        return any(pattern.match(line) for pattern in cls.NOISE_LINE_PATTERNS)

    @classmethod
    def _strip_chrome(cls, soup: "BeautifulSoup") -> None:
        """
        Remove menu, popup and widget wrappers matched by class.

        Targets are collected first and decomposed afterwards: decomposing a parent clears the
        attributes of its descendants, so inspecting a child mid-loop raises.
        """
        targets = []
        for element in soup.find_all(True):
            classes = element.get("class") or []
            if any(token in cls.NOISE_CLASS_TOKENS for token in classes) or any(
                token.startswith(prefix) for token in classes for prefix in cls.NOISE_CLASS_PREFIXES
            ):
                targets.append(element)
        for element in targets:
            if element.parent is not None:
                element.decompose()

    @classmethod
    def _page_text(cls, html: str, url: str) -> Dict[str, Any]:
        """
        Extract the readable content of one HTML page.

        Prefers the semantic main/article region when the site provides one, otherwise falls
        back to the body. Navigation, forms, menus and duplicated chrome are stripped so the
        resulting text is what a visitor actually reads.
        """
        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.get_text(strip=True) if soup.title else url

        # Read description/structured data first: they live in <head>, which the chrome stripping
        # below is entitled to remove.
        structured = cls._meta_and_jsonld(soup)

        # Collect links before anything is decomposed, so navigation links still lead the crawl
        # into the rest of the site.
        links = []
        for anchor in soup.find_all("a", href=True):
            absolute = urljoin(url, anchor["href"])
            if absolute not in links:
                links.append(absolute)

        for element in soup(cls.NOISE_TAGS):
            element.decompose()
        for element in soup.find_all(attrs={"role": ["navigation", "banner", "contentinfo", "search"]}):
            element.decompose()
        cls._strip_chrome(soup)

        container = soup.find("main") or soup.find("article") or soup.body or soup
        raw_text = container.get_text(separator="\n")

        # Collapse per-line repetition (theme taglines repeated in every block) and blank lines.
        seen_lines, kept_lines = set(), []
        for line in raw_text.splitlines():
            stripped = re.sub(r"\s+", " ", line).strip()
            if not stripped or cls._is_noise_line(stripped):
                continue
            key = stripped.lower()
            if key in seen_lines:
                continue
            seen_lines.add(key)
            kept_lines.append(stripped)

        body_text = cls.clean_text("\n".join(kept_lines))
        # A thin body means the copy is rendered client-side. Fall back to the description and
        # structured data rather than storing a page that can only produce refusals.
        if len(body_text) < 400 and structured:
            body_text = cls.clean_text(f"{body_text}\n{structured}") if body_text else structured

        return {
            "url": url,
            "title": page_title,
            "text": body_text,
            "links": links,
        }

    @classmethod
    def crawl_website(
        cls,
        url: str,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Crawl the site the seed URL belongs to, breadth-first, and return its combined text.

        Defaults to many pages because a business site is many pages: fetching only the homepage
        gave the bot a paragraph about the company and nothing about products, branches or
        policies, which is why every question past the homepage was answered with a refusal.

        Scope is the whole host, not the seed's sub-path. Requiring every URL to sit under the
        seed path meant that starting at ``/about`` crawled one page, and starting at a product
        page crawled nothing else. Junk paths are filtered instead, and links are ranked so the
        seed's own section is fetched first.

        Depth is capped at 2 and the run has a wall-clock budget, so this stays bounded even on a
        site with thousands of links.
        """
        base = urlparse(url)
        if base.scheme not in ("http", "https") or not base.netloc:
            raise ValueError("Please provide a full http:// or https:// URL.")

        max_pages = max(1, min(int(max_pages or cls.MAX_CRAWL_PAGES), cls.MAX_CRAWL_PAGES))
        max_depth = max(0, min(int(max_depth if max_depth is not None else cls.MAX_CRAWL_DEPTH),
                               cls.MAX_CRAWL_DEPTH))
        seed = cls._normalise_url(url)
        if not seed:
            raise ValueError("Please provide a full http:// or https:// URL.")

        pages: List[Dict[str, Any]] = []
        queued = {seed}
        seen_text = set()
        truncated = False
        deadline = time.monotonic() + cls.CRAWL_TIME_BUDGET_SECONDS
        total_chars = 0

        # Redirects are followed manually so every hop is re-validated (SSRF via an open
        # redirect or a DNS name that flips to a private address after the first check).
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            # The seed is fetched first because the site may redirect (pateljewellers.com ->
            # www.pateljewellers.com). Judging later links against the original host rejected
            # every page on the site, which is why a crawl of 30 returned exactly one.
            html, status_code, final_url = cls._fetch_html(client, seed)
            scope = urlparse(final_url)
            if scope.netloc and scope.netloc.lower() != base.netloc.lower():
                logger.info("Crawl scope follows redirect: %s -> %s", base.netloc, scope.netloc)

            page = cls._page_text(html, final_url)
            page["status_code"] = status_code
            if not page["text"]:
                raise ValueError(
                    "No readable text could be extracted from this URL. The page may be blocked, "
                    "empty, or require JavaScript rendering."
                )
            pages.append(page)
            total_chars += len(page["text"])
            seen_text.add(page["text"][:400])

            queue: List[Tuple[str, int]] = []
            # A sitemap lists canonical pages even when the homepage links few of them.
            for discovered in cls._sitemap_urls(client, scope):
                if discovered not in queued:
                    queued.add(discovered)
                    queue.append((discovered, 1))
            for link in cls._rank_links(page["links"], scope):
                normalised = cls._normalise_url(link)
                if normalised and normalised not in queued and normalised != cls._normalise_url(final_url):
                    queued.add(normalised)
                    queue.append((normalised, 1))

            index = 0
            while index < len(queue) and len(pages) < max_pages:
                if time.monotonic() > deadline or total_chars >= cls.MAX_CRAWL_CHARS:
                    truncated = True
                    break
                current, depth = queue[index]
                index += 1
                try:
                    html, status_code, final_url = cls._fetch_html(client, current)
                except Exception as exc:
                    logger.warning(f"Crawl skipped {current}: {exc}")
                    if not pages and current == seed:
                        raise
                    continue

                page = cls._page_text(html, final_url)
                page["status_code"] = status_code
                if not page["text"]:
                    continue

                # Near-identical pages (language variants, colour/filter duplicates) add cost to
                # every question without adding an answer.
                fingerprint = page["text"][:400]
                if fingerprint in seen_text:
                    continue
                seen_text.add(fingerprint)

                pages.append(page)
                total_chars += len(page["text"])

                if depth < max_depth:
                    for link in cls._rank_links(page["links"], scope):
                        normalised = cls._normalise_url(link)
                        if not normalised or normalised in queued:
                            continue
                        if len(queued) >= max_pages * 4:
                            truncated = True
                            break
                        queued.add(normalised)
                        queue.append((normalised, depth + 1))

        if not pages:
            raise ValueError(
                "No readable text could be extracted from this URL. The page may be blocked, "
                "empty, or require JavaScript rendering."
            )

        sections = []
        for page in pages:
            header = f"PAGE: {page['title']}\nURL: {page['url']}"
            sections.append(f"{header}\n\n{page['text']}")
        combined_text = cls.clean_text("\n\n".join(sections))

        # A page that yields almost nothing is usually a JS-rendered shell. Storing that would
        # give the bot a knowledge source that can only ever produce refusals.
        if len(combined_text) < cls.MIN_CRAWL_CHARS:
            raise ValueError(
                "This page returned almost no readable text (it may need JavaScript rendering or "
                "block automated access). Try another URL, or upload the content as a document."
            )

        metadata = {
            "url": url,
            "page_title": pages[0]["title"],
            "status_code": pages[0].get("status_code"),
            "pages_crawled": len(pages),
            "discovered_urls": len(queued),
            "truncated": truncated,
            # Surfaced so the UI can say "only 1 page was readable" instead of letting the owner
            # assume the whole site is in the bot's head.
            "coverage_warning": (
                None
                if len(pages) > 1
                else "Only the seed page had readable text. Other pages may need JavaScript."
            ),
            "pages": [
                {
                    "url": page["url"],
                    "title": page["title"],
                    "character_count": len(page["text"]),
                    "text": page["text"],
                }
                for page in pages
            ],
            "character_count": len(combined_text),
            "parser": "beautifulsoup4+crawler",
        }
        return combined_text, metadata

    @staticmethod
    def extract_from_website(url: str) -> Tuple[str, Dict[str, Any]]:
        """Backwards-compatible single-page extraction used by callers that pass no depth."""
        return DocumentProcessor.crawl_website(url, max_pages=1)
