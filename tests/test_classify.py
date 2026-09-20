from core.classify import classify_email


def _email(**kwargs):
    base = {"email_id": "email_x", "from": "a@aprilasia.com", "subject": "", "body": "", "attachments": []}
    base.update(kwargs)
    return base


def test_spam_by_known_bad_domain():
    cat, _ = classify_email(_email(**{
        "from": "winner@prize-claims.info",
        "subject": "Exclusive offer",
        "body": "Please reply with your bank details.",
    }))
    assert cat.value == "SPAM"


def test_bl_comparison_by_attachment_presence():
    cat, _ = classify_email(_email(attachments=["attachments/email_004_SI.txt", "attachments/email_004_BL.txt"]))
    assert cat.value == "BL_COMPARISON"


def test_bl_comparison_by_explicit_compare_intent_without_attachment():
    cat, _ = classify_email(_email(
        subject="TO CONFIRM DOCS",
        body="Please compare the SI and draft BL for PSGSE8356691 and confirm (attachments appear to have been dropped).",
    ))
    assert cat.value == "BL_COMPARISON"


def test_send_bl_request_without_attachment_is_general_not_comparison():
    cat, _ = classify_email(_email(
        subject="Draft BL MMSS 2507 V.257087E",
        body="Please assist to send the draft BL for PSGSE9638346 for checking asap.",
    ))
    assert cat.value == "GENERAL"


def test_invoice_query():
    cat, _ = classify_email(_email(
        subject="Total Freight - INDIA",
        body="Query on invoice 5250071354: is the THC / local charge included or billed separately?",
    ))
    assert cat.value == "INVOICE_QUERY"


def test_si_request():
    cat, _ = classify_email(_email(
        subject="REQUEST SI _ 5RFR-37631",
        body="Please find Shipping instruction for 5RFR-37631.\nPOL: SINGAPORE\nPOD: GDANSK, POLAND",
    ))
    assert cat.value == "SI_REQUEST"


def test_general_fallback():
    cat, _ = classify_email(_email(
        subject="15_01_2026 - UPDATE SUMMARY",
        body="Please find attached the list of outstanding BL. Kindly action the pending items.",
    ))
    assert cat.value == "GENERAL"
