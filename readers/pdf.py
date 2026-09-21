import io
import logging

import pdfplumber
import pypdfium2 as pdfium

from core.models import DocumentExtraction
from llm.gemini_client import extract_from_images, extract_from_text
from readers.dispatch import register

logger = logging.getLogger(__name__)

MIN_TEXT_LEN = 40  # a page needs at least this many chars to count as "has real text"
MAX_PAGES = 5
MAX_TEXT_PAGES = 200
MAX_TEXT_CHARS = 100_000


def read_pdf(data: bytes, role: str, filename: str) -> DocumentExtraction:
    pages, truncated = _extract_text_per_page(data)
    if truncated:
        # Can't confidently claim we read the whole document — escalate
        # rather than silently sending a truncated/costly prompt to Gemini.
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)

    # Route per page, not on total text length: a scanned PDF with just a
    # 40+ char footer/stamp on one page would otherwise trip a
    # total-length threshold and send Gemini only that footer, silently
    # missing every real field on the other (image-only) pages.
    if pages and all(len(p) >= MIN_TEXT_LEN for p in pages):
        text = "\n".join(pages).strip()
        if len(text) > MAX_TEXT_CHARS:
            return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)
        return extract_from_text(data, text, role, filename)

    images = _render_pages_to_png(data)
    if not images:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)
    return extract_from_images(data, images, role, filename)


def _extract_text_per_page(data: bytes) -> tuple[list[str], bool]:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            truncated = len(pdf.pages) > MAX_TEXT_PAGES
            pages = [(page.extract_text() or "").strip() for page in pdf.pages[:MAX_TEXT_PAGES]]
        return pages, truncated
    except Exception as e:
        logger.warning("PDF text extraction failed: %s: %s", type(e).__name__, e)
        return [], False


def _render_pages_to_png(data: bytes, dpi: int = 200) -> list[bytes]:
    pdf = None
    try:
        pdf = pdfium.PdfDocument(data)
        scale = dpi / 72
        images = []
        for i in range(min(len(pdf), MAX_PAGES)):
            bitmap = pdf[i].render(scale=scale)
            pil_image = bitmap.to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            images.append(buf.getvalue())
        return images
    except Exception as e:
        logger.warning("PDF page rendering failed: %s: %s", type(e).__name__, e)
        return []
    finally:
        if pdf is not None:
            pdf.close()


register("pdf", read_pdf)
