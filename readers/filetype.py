"""Magic-byte file type detection. Never trust the filename extension."""

MAX_BYTES = 25 * 1024 * 1024  # 25 MB safety cap
PDF_HEADER_SEARCH_WINDOW = 1024  # some real-world PDFs have junk/a BOM before "%PDF-"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


class UnsupportedFileError(Exception):
    pass


def detect(data: bytes) -> str:
    """Return one of: 'pdf', 'docx', 'xlsx', 'txt', 'unknown'."""
    if len(data) > MAX_BYTES:
        return "unknown"
    if not data:
        return "unknown"
    if b"%PDF-" in data[:PDF_HEADER_SEARCH_WINDOW]:
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        # docx/xlsx are both zip containers; distinguish by internal manifest names.
        return _detect_zip_office(data)
    if _looks_like_text(data):
        return "txt"
    return "unknown"


def _detect_zip_office(data: bytes) -> str:
    import zipfile
    import io

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            if any(n.startswith("word/") for n in names):
                return "docx"
            if any(n.startswith("xl/") for n in names):
                return "xlsx"
    except zipfile.BadZipFile:
        return "unknown"
    return "unknown"


def _looks_like_text(data: bytes) -> bool:
    """latin-1 never fails to decode, so "try to decode it" alone can't
    distinguish text from binary garbage. Use an actual content signal
    instead: a NUL byte anywhere (UTF-16 files aside) or more than a
    trace of control characters means binary.
    """
    if data[:2] in _UTF16_BOMS:
        return True
    if b"\x00" in data:
        return False
    control_bytes = sum(1 for b in data if b < 0x20 and b not in (0x09, 0x0A, 0x0D))
    return control_bytes / len(data) < 0.01
