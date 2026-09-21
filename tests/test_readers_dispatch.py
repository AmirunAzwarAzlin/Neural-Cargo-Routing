from readers.dispatch import read_document


def test_read_document_decodes_cp1252_text_without_mangling_accents(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    text = "SHIPPING INSTRUCTION\nShipper: SOCIÉTÉ GÉNÉRALE\n"
    (data_dir / "email_001_SI.txt").write_bytes(text.encode("cp1252"))

    result = read_document(str(data_dir), "email_001_SI.txt", "SI")

    assert "SOCIÉTÉ GÉNÉRALE" == result.fields["shipper"].raw_value
    assert "�" not in (result.raw_text or "")
