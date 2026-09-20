#!/usr/bin/env python3
"""Validates a submission.json against the shape of data/sample_submission.json:
same email_id keys, same field names/types, valid enum values, ordering rules."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings

VALID_CATEGORIES = {"BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"}
VALID_STATUSES = {"OK", "MISMATCH", "NEEDS_REVIEW"}
VALID_REASONS = {"wrong_doc_type", "missing_attachment", "unreadable", "missing_value", None}
REQUIRED_KEYS = {"category", "status", "review_reason", "defect_fields", "has_defect"}


def validate(submission_path: str, sample_path: str) -> list[str]:
    errors = []
    submission = json.loads(Path(submission_path).read_text(encoding="utf-8"))
    sample = json.loads(Path(sample_path).read_text(encoding="utf-8"))

    missing_ids = set(sample) - set(submission)
    extra_ids = set(submission) - set(sample)
    if missing_ids:
        errors.append(f"Missing {len(missing_ids)} email_ids, e.g. {sorted(missing_ids)[:5]}")
    if extra_ids:
        errors.append(f"{len(extra_ids)} unexpected email_ids, e.g. {sorted(extra_ids)[:5]}")

    for eid, entry in submission.items():
        if eid not in sample:
            continue
        keys = set(entry.keys())
        if keys != REQUIRED_KEYS:
            errors.append(f"{eid}: keys {keys} != {REQUIRED_KEYS}")
            continue
        if entry["category"] not in VALID_CATEGORIES:
            errors.append(f"{eid}: invalid category {entry['category']!r}")
        if entry["status"] not in VALID_STATUSES:
            errors.append(f"{eid}: invalid status {entry['status']!r}")
        if entry["review_reason"] not in VALID_REASONS:
            errors.append(f"{eid}: invalid review_reason {entry['review_reason']!r}")
        if not isinstance(entry["defect_fields"], list):
            errors.append(f"{eid}: defect_fields is not a list")
        if not isinstance(entry["has_defect"], bool):
            errors.append(f"{eid}: has_defect is not a bool")

        status, reason, has_defect, defects = (
            entry["status"], entry["review_reason"], entry["has_defect"], entry["defect_fields"],
        )
        if status == "NEEDS_REVIEW" and reason is None:
            errors.append(f"{eid}: NEEDS_REVIEW without review_reason")
        if status != "NEEDS_REVIEW" and reason is not None:
            errors.append(f"{eid}: review_reason set but status is {status}")
        if status == "MISMATCH" and (not has_defect or not defects):
            errors.append(f"{eid}: MISMATCH must have has_defect=true and non-empty defect_fields")
        if status == "OK" and (has_defect or defects):
            errors.append(f"{eid}: OK must have has_defect=false and empty defect_fields")
        if status == "NEEDS_REVIEW" and (has_defect or defects):
            errors.append(f"{eid}: NEEDS_REVIEW must have has_defect=false and empty defect_fields")

    return errors


def main():
    submission_path = sys.argv[1] if len(sys.argv) > 1 else "submission.json"
    sample_path = sys.argv[2] if len(sys.argv) > 2 else str(Path(settings.data_dir) / "sample_submission.json")
    errors = validate(submission_path, sample_path)
    if errors:
        print(f"INVALID: {len(errors)} problem(s)")
        for e in errors[:50]:
            print(" -", e)
        sys.exit(1)
    print("VALID: submission.json matches the required shape.")


if __name__ == "__main__":
    main()
