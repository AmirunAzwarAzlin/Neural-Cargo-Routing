import json

from scripts.validate_submission import validate


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_valid_submission_passes(tmp_path):
    sample = {"email_001": {"category": "GENERAL", "status": "OK", "review_reason": None,
                             "defect_fields": [], "has_defect": False}}
    submission = dict(sample)
    sample_path = _write(tmp_path, "sample.json", sample)
    sub_path = _write(tmp_path, "submission.json", submission)
    assert validate(sub_path, sample_path) == []


def test_missing_email_id_is_flagged(tmp_path):
    sample = {"email_001": {}, "email_002": {}}
    submission = {"email_001": {"category": "GENERAL", "status": "OK", "review_reason": None,
                                 "defect_fields": [], "has_defect": False}}
    sample_path = _write(tmp_path, "sample.json", sample)
    sub_path = _write(tmp_path, "submission.json", submission)
    errors = validate(sub_path, sample_path)
    assert any("email_002" in e for e in errors)


def test_mismatch_without_defect_fields_is_flagged(tmp_path):
    sample = {"email_001": {}}
    submission = {"email_001": {"category": "BL_COMPARISON", "status": "MISMATCH", "review_reason": None,
                                 "defect_fields": [], "has_defect": True}}
    sample_path = _write(tmp_path, "sample.json", sample)
    sub_path = _write(tmp_path, "submission.json", submission)
    errors = validate(sub_path, sample_path)
    assert any("MISMATCH" in e for e in errors)
