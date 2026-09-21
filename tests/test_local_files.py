import pytest

from storage.local_files import read_attachment_bytes


def test_read_attachment_bytes_reads_within_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "email_001_SI.txt").write_bytes(b"hello")

    assert read_attachment_bytes(str(data_dir), "email_001_SI.txt") == b"hello"


def test_read_attachment_bytes_reads_within_nested_subdir(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "attachments").mkdir(parents=True)
    (data_dir / "attachments" / "a.txt").write_bytes(b"nested")

    assert read_attachment_bytes(str(data_dir), "attachments/a.txt") == b"nested"


def test_read_attachment_bytes_rejects_dotdot_traversal(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"top secret")

    with pytest.raises(ValueError):
        read_attachment_bytes(str(data_dir), "../secret.txt")


def test_read_attachment_bytes_rejects_absolute_path(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"top secret")

    with pytest.raises(ValueError):
        read_attachment_bytes(str(data_dir), str(secret))
