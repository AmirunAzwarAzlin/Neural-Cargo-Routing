"""Reader-dispatch tests for non-.txt formats. Gemini calls are monkeypatched
so this suite runs offline, deterministically, and at no API cost."""
import io

import openpyxl
from docx import Document

from core.models import DocumentExtraction, FieldState


def test_docx_reader_extracts_paragraphs_and_tables_then_calls_gemini(monkeypatch):
    doc = Document()
    doc.add_paragraph("BILL OF LADING (DRAFT)")
    doc.add_paragraph("Shipper: TEST SHIPPER CO")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Consignee"
    table.rows[0].cells[1].text = "TEST CONSIGNEE CO"
    buf = io.BytesIO()
    doc.save(buf)
    data = buf.getvalue()

    captured = {}

    def fake_extract_from_text(document_bytes, document_text, role, filename):
        captured["text"] = document_text
        captured["role"] = role
        return DocumentExtraction(role=role, filename=filename, doc_kind="BL", readable=True)

    import readers.docx as docx_reader
    monkeypatch.setattr(docx_reader, "extract_from_text", fake_extract_from_text)

    result = docx_reader.read_docx(data, "BL", "att.docx")

    assert "Shipper: TEST SHIPPER CO" in captured["text"]
    assert "Consignee | TEST CONSIGNEE CO" in captured["text"]
    assert result.doc_kind == "BL"


def test_docx_reader_marks_unreadable_on_corrupt_bytes():
    import readers.docx as docx_reader

    result = docx_reader.read_docx(b"not a real docx", "SI", "att.docx")
    assert result.readable is False
    assert result.doc_kind == "UNKNOWN"


def test_xlsx_reader_dumps_cells_and_calls_gemini(monkeypatch):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "Shipper"
    ws["B1"] = "TEST SHIPPER CO"
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    captured = {}

    def fake_extract_from_text(document_bytes, document_text, role, filename):
        captured["text"] = document_text
        return DocumentExtraction(role=role, filename=filename, doc_kind="SI", readable=True)

    import readers.xlsx as xlsx_reader
    monkeypatch.setattr(xlsx_reader, "extract_from_text", fake_extract_from_text)

    result = xlsx_reader.read_xlsx(data, "SI", "att.xlsx")

    assert "Sheet1!A1: Shipper" in captured["text"]
    assert "Sheet1!B1: TEST SHIPPER CO" in captured["text"]
    assert result.doc_kind == "SI"


def test_xlsx_reader_marks_unreadable_on_corrupt_bytes():
    import readers.xlsx as xlsx_reader

    result = xlsx_reader.read_xlsx(b"not a real xlsx", "BL", "att.xlsx")
    assert result.readable is False


def test_pdf_reader_uses_text_path_when_text_present(monkeypatch):
    import readers.pdf as pdf_reader

    monkeypatch.setattr(pdf_reader, "_extract_text", lambda data: "Shipper: TEST CO\n" * 5)
    called = {}

    def fake_extract_from_text(document_bytes, document_text, role, filename):
        called["used_text_path"] = True
        return DocumentExtraction(role=role, filename=filename, doc_kind="SI", readable=True)

    monkeypatch.setattr(pdf_reader, "extract_from_text", fake_extract_from_text)
    result = pdf_reader.read_pdf(b"fake-pdf-bytes", "SI", "att.pdf")

    assert called.get("used_text_path") is True
    assert result.doc_kind == "SI"


def test_pdf_reader_falls_back_to_vision_when_no_text(monkeypatch):
    import readers.pdf as pdf_reader

    monkeypatch.setattr(pdf_reader, "_extract_text", lambda data: "")
    monkeypatch.setattr(pdf_reader, "_render_pages_to_png", lambda data: [b"fake-png-bytes"])
    called = {}

    def fake_extract_from_images(document_bytes, images, role, filename):
        called["used_vision_path"] = True
        return DocumentExtraction(role=role, filename=filename, doc_kind="BL", readable=True)

    monkeypatch.setattr(pdf_reader, "extract_from_images", fake_extract_from_images)
    result = pdf_reader.read_pdf(b"fake-pdf-bytes", "BL", "att.pdf")

    assert called.get("used_vision_path") is True
    assert result.doc_kind == "BL"


def test_pdf_reader_unreadable_when_no_text_and_no_images(monkeypatch):
    import readers.pdf as pdf_reader

    monkeypatch.setattr(pdf_reader, "_extract_text", lambda data: "")
    monkeypatch.setattr(pdf_reader, "_render_pages_to_png", lambda data: [])

    result = pdf_reader.read_pdf(b"corrupt-bytes", "SI", "att.pdf")
    assert result.readable is False
    assert result.doc_kind == "UNKNOWN"
