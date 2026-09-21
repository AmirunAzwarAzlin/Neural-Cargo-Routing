import io

import pdfplumber
import pypdfium2 as pdfium

from core.models import DocumentExtraction
from llm.gemini_client import extract_from_images, extract_from_text
from readers.dispatch import register

MIN_TEXT_LEN = 40
MAX_PAGES = 5
MAX_TEXT_PAGES = 200
MAX_TEXT_CHARS = 100_000


def read_pdf(data: bytes, role: str, filename: str) -> DocumentExtraction:
    text, truncated = _extract_text(data)
    if truncated:
        # Can't confidently claim we read the whole document — escalate
        # rather than silently sending a truncated/costly prompt to Gemini.
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)
    if len(text) >= MIN_TEXT_LEN:
        return extract_from_text(data, text, role, filename)

    images = _render_pages_to_png(data)
    if not images:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)
    return extract_from_images(data, images, role, filename)


def _extract_text(data: bytes) -> tuple[str, bool]:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count_truncated = len(pdf.pages) > MAX_TEXT_PAGES
            parts = [page.extract_text() or "" for page in pdf.pages[:MAX_TEXT_PAGES]]
        text = "\n".join(parts).strip()
        char_truncated = len(text) > MAX_TEXT_CHARS
        return text[:MAX_TEXT_CHARS], (page_count_truncated or char_truncated)
    except Exception:
        return "", False


def _render_pages_to_png(data: bytes, dpi: int = 200) -> list[bytes]:
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
    except Exception:
        return []


register("pdf", read_pdf)
