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


def test_detect_pdf_tolerates_leading_junk_bytes():
    assert detect(b"\xef\xbb\xbf   \n%PDF-1.4\n...") == "pdf"


def test_detect_utf16_text_not_misclassified_as_binary():
    data = b"\xff\xfe" + "SHIPPING INSTRUCTION\nShipper: X\n".encode("utf-16-le")
    assert detect(data) == "txt"


def test_detect_checks_whole_file_for_nul_not_just_first_4096_bytes():
    data = b"A" * 5000 + b"\x00" + b"B" * 100
    assert detect(data) == "unknown"


def test_detect_cp1252_text_with_accented_chars_is_still_text():
    data = "SOCIÉTÉ GÉNÉRALE\nShipper: X\n".encode("cp1252")
    assert detect(data) == "txt"
