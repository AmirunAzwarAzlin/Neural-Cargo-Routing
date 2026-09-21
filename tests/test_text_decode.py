from readers.text_decode import decode_bytes


def test_decode_utf8():
    assert decode_bytes("SOCIÉTÉ".encode("utf-8")) == "SOCIÉTÉ"


def test_decode_utf8_with_bom_strips_bom():
    data = b"\xef\xbb\xbf" + "SOCIÉTÉ".encode("utf-8")
    result = decode_bytes(data)
    assert result == "SOCIÉTÉ"
    assert not result.startswith("﻿")


def test_decode_cp1252_fallback_when_not_valid_utf8():
    data = "SOCIÉTÉ".encode("cp1252")
    assert decode_bytes(data) == "SOCIÉTÉ"


def test_decode_utf16_le_by_bom():
    data = "SOCIÉTÉ".encode("utf-16-le")
    data = b"\xff\xfe" + data
    assert decode_bytes(data) == "SOCIÉTÉ"


def test_decode_never_raises_on_arbitrary_bytes():
    decode_bytes(bytes(range(256)))  # must not raise
