"""Dispatches an attachment to the right reader based on magic-byte file type."""
from core.extract_rules import parse_txt_document
from core.models import DocumentExtraction
from readers import filetype
from readers.text_decode import decode_bytes
from storage.local_files import read_attachment_bytes

_NON_TXT_READERS = {}  # filled in by readers.pdf / readers.docx / readers.xlsx via register()


def register(kind: str, fn) -> None:
    _NON_TXT_READERS[kind] = fn


def read_document(data_dir: str, att_path: str, role: str) -> DocumentExtraction:
    data = read_attachment_bytes(data_dir, att_path)
    kind = filetype.detect(data)

    if kind == "txt":
        text = decode_bytes(data)
        return parse_txt_document(text, role, filename=att_path)

    reader = _NON_TXT_READERS.get(kind)
    if reader is not None:
        return reader(data, role, att_path)

    return DocumentExtraction(
        role=role,
        filename=att_path,
        doc_kind="UNKNOWN",
        readable=False,
        raw_text=None,
    )


def _register_builtin_readers() -> None:
    # imported here (not at module top) so these modules can import `register`
    # from this module without a circular-import failure at load time.
    import readers.docx  # noqa: F401
    import readers.pdf  # noqa: F401
    import readers.xlsx  # noqa: F401


_register_builtin_readers()
