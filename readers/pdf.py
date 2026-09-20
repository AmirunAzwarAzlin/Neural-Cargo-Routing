import io

import pdfplumber
import pypdfium2 as pdfium

from core.models import DocumentExtraction
from llm.gemini_client import extract_from_images, extract_from_text
from readers.dispatch import register

MIN_TEXT_LEN = 40
MAX_PAGES = 5


def read_pdf(data: bytes, role: str, filename: str) -> DocumentExtraction:
    text = _extract_text(data)
    if len(text) >= MIN_TEXT_LEN:
        return extract_from_text(data, text, role, filename)

    images = _render_pages_to_png(data)
    if not images:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)
    return extract_from_images(data, images, role, filename)


def _extract_text(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            parts = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(parts).strip()
    except Exception:
        return ""


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
