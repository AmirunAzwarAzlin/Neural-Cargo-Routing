from readers.filetype import detect


def test_detect_pdf():
    assert detect(b"%PDF-1.4\n...") == "pdf"


def test_detect_txt():
    assert detect(b"SHIPPING INSTRUCTION\nShipper: X\n") == "txt"


def test_detect_unknown_binary():
    assert detect(b"\x00\x01\x02\x03garbage") == "unknown"


def test_detect_empty():
    assert detect(b"") == "unknown"


def test_detect_docx():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<xml/>")
        zf.writestr("[Content_Types].xml", "<xml/>")
    assert detect(buf.getvalue()) == "docx"


def test_detect_xlsx():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", "<xml/>")
        zf.writestr("[Content_Types].xml", "<xml/>")
    assert detect(buf.getvalue()) == "xlsx"
