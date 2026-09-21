import io

from openpyxl import load_workbook

from core.models import DocumentExtraction
from llm.gemini_client import extract_from_text
from readers.dispatch import register
from readers.zip_safety import UnsafeZipError, check_zip_bomb_safety

MAX_TEXT_CHARS = 100_000
MAX_CELLS = 50_000


def read_xlsx(data: bytes, role: str, filename: str) -> DocumentExtraction:
    try:
        check_zip_bomb_safety(data)
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except (UnsafeZipError, Exception):
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)

    lines = []
    cell_count = 0
    truncated = False
    for sheet in wb.worksheets:
        if sheet.sheet_state != "visible":
            continue  # a defect hidden in a hidden sheet must not go unseen silently either way — skip, don't guess
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    if cell_count >= MAX_CELLS:
                        truncated = True
                        break
                    lines.append(f"{sheet.title}!{cell.coordinate}: {cell.value}")
                    cell_count += 1
            if truncated:
                break
        if truncated:
            break
    text = "\n".join(lines).strip()

    if not text:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)

    if truncated or len(text) > MAX_TEXT_CHARS:
        # Can't confidently read the whole sheet — escalate rather than
        # silently sending a truncated/costly prompt to Gemini.
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)

    return extract_from_text(data, text, role, filename)


register("xlsx", read_xlsx)
