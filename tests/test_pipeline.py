from core.pipeline import process_email_safe

BL_EMAIL = {
    "email_id": "email_999",
    "from": "ops@aprilasia.com",
    "subject": "SI/BL check",
    "body": "please check the details and confirm",
    "attachments": ["foo_SI.txt", "foo_BL.txt"],
}

GENERAL_EMAIL = {
    "email_id": "email_998",
    "from": "ops@aprilasia.com",
    "subject": "hello",
    "body": "just saying hi",
    "attachments": [],
}


def test_process_email_safe_escalates_on_generic_extractor_error():
    def boom(att_path, role):
        raise RuntimeError("gemini exploded")

    result = process_email_safe(BL_EMAIL, boom)

    assert result.email_id == "email_999"
    assert result.comparison.status.value == "NEEDS_REVIEW"
    assert result.comparison.review_reason.value == "unreadable"


def test_process_email_safe_reports_missing_attachment_on_file_not_found():
    def boom(att_path, role):
        raise FileNotFoundError(att_path)

    result = process_email_safe(BL_EMAIL, boom)

    assert result.comparison.status.value == "NEEDS_REVIEW"
    assert result.comparison.review_reason.value == "missing_attachment"


def test_process_email_safe_passes_through_on_success():
    def ok(att_path, role):
        from core.models import DocumentExtraction

        return DocumentExtraction(role=role, doc_kind="UNKNOWN", readable=False)

    result = process_email_safe(BL_EMAIL, ok)

    assert result.email_id == "email_999"
    assert result.comparison.status.value == "NEEDS_REVIEW"
    assert result.comparison.review_reason.value == "unreadable"


def test_process_email_safe_does_not_touch_non_bl_comparison_emails():
    def unused(att_path, role):
        raise AssertionError("extractor should not be called")

    result = process_email_safe(GENERAL_EMAIL, unused)

    assert result.category.value == "GENERAL"
    assert result.comparison is None
