import json
import sys

import scripts.run_pipeline as run_pipeline

EMAILS = [
    {
        "email_id": "email_A",
        "from": "ops@aprilasia.com",
        "subject": "SI/BL check",
        "body": "please check the details and confirm",
        "attachments": ["a_SI.txt", "a_BL.txt"],
    },
    {
        "email_id": "email_B",
        "from": "ops@aprilasia.com",
        "subject": "hello",
        "body": "just saying hi",
        "attachments": [],
    },
]


def test_one_failing_email_does_not_lose_the_whole_run(tmp_path, monkeypatch):
    out_path = tmp_path / "submission.json"

    monkeypatch.setattr(run_pipeline, "list_emails", lambda data_dir: EMAILS)

    def boom_extractor(data_dir, att_path, role):
        raise RuntimeError(f"exploded on {att_path}")

    monkeypatch.setattr(run_pipeline, "read_document", boom_extractor)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--out", str(out_path)])

    run_pipeline.main()  # must not raise

    submission = json.loads(out_path.read_text(encoding="utf-8"))
    assert set(submission.keys()) == {"email_A", "email_B"}
    assert submission["email_A"]["status"] == "NEEDS_REVIEW"
    assert submission["email_A"]["review_reason"] in ("unreadable", "missing_attachment")
    assert submission["email_B"]["status"] == "OK"
