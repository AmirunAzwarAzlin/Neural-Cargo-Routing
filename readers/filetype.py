"""Magic-byte file type detection. Never trust the filename extension."""

MAX_BYTES = 25 * 1024 * 1024  # 25 MB safety cap


class UnsupportedFileError(Exception):
    pass


def detect(data: bytes) -> str:
    """Return one of: 'pdf', 'docx', 'xlsx', 'txt', 'unknown'."""
    if len(data) > MAX_BYTES:
        return "unknown"
    if not data:
        return "unknown"
    if data.startswith(b"%PDF-"):
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
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            sample.decode("latin-1")
            return True
        except UnicodeDecodeError:
            return False
