import io

from openpyxl import load_workbook

from core.models import DocumentExtraction
from llm.gemini_client import extract_from_text
from readers.dispatch import register


def read_xlsx(data: bytes, role: str, filename: str) -> DocumentExtraction:
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)

    lines = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    lines.append(f"{sheet.title}!{cell.coordinate}: {cell.value}")
    text = "\n".join(lines).strip()

    if not text:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)
    return extract_from_text(data, text, role, filename)


register("xlsx", read_xlsx)
