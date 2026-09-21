"""Minimal local-filesystem access to the SDOC data bundle (inbox/ + attachments/)."""
import json
from pathlib import Path


def list_emails(data_dir: str) -> list[dict]:
    inbox_dir = Path(data_dir) / "inbox"
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(inbox_dir.glob("email_*.json"))
    ]


def read_attachment_bytes(data_dir: str, att_path: str) -> bytes:
    if Path(att_path).is_absolute():
        raise ValueError(f"attachment path must be relative: {att_path!r}")
    base = Path(data_dir).resolve()
    target = (base / att_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"attachment path escapes data_dir: {att_path!r}")
    return target.read_bytes()
