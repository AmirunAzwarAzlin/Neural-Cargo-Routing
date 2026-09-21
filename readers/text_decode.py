"""One shared decode used by both file-type detection and actual text
reading, so they never disagree about what a file's text is. UTF-8 is
tried first (most of the dataset); cp1252/latin-1 is the fallback for
older Windows-authored .txt exports (accented company names etc.) instead
of blindly decoding everything as UTF-8 with lossy replacement characters.
"""

_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_UTF8_BOM = b"\xef\xbb\xbf"


def decode_bytes(data: bytes) -> str:
    if data[:2] in _UTF16_BOMS:
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if data.startswith(_UTF8_BOM):
        return data.decode("utf-8-sig")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1252")
    except UnicodeDecodeError:
        return data.decode("latin-1")  # never fails: last resort
