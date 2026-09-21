import io
import zipfile

import pytest

from readers.zip_safety import UnsafeZipError, check_zip_bomb_safety


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_normal_small_zip_passes():
    data = _make_zip({"word/document.xml": b"<xml>hello</xml>"})
    check_zip_bomb_safety(data)  # must not raise


def test_rejects_zip_whose_declared_uncompressed_size_exceeds_cap():
    data = _make_zip({"xl/sheet1.xml": b"0" * 5000})
    with pytest.raises(UnsafeZipError):
        check_zip_bomb_safety(data, max_uncompressed_bytes=1000)


def test_rejects_zip_with_too_many_entries():
    data = _make_zip({f"f{i}.xml": b"x" for i in range(50)})
    with pytest.raises(UnsafeZipError):
        check_zip_bomb_safety(data, max_entries=10)


def test_rejects_invalid_zip_data():
    with pytest.raises(UnsafeZipError):
        check_zip_bomb_safety(b"not a zip file at all")
