from core.decide import decide
from core.extract_rules import parse_txt_document

SI_TEXT = """SHIPPING INSTRUCTION
Shipper: A CO
Consignee: B CO
Notify Party: C CO
Port of Loading: SINGAPORE
Discharge Port: TOKYO, JAPAN
No. of Containers: 3 x 40'HC
Gross Weight (KG): 22,000 KG
"""

BL_TEXT_MATCH = """BILL OF LADING (DRAFT)
Shipper: A CO
Consignee: B CO
Notify: C CO
Port of Loading: SINGAPORE
POD: TOKYO, JAPAN
Container Count: 3 x 40'HC
Gross Wt (kgs): 22,000 KG
"""

BL_TEXT_MISMATCH_CONTAINERS = BL_TEXT_MATCH.replace("3 x 40'HC", "4 x 40'HC")

BL_TEXT_MISSING_WEIGHT = BL_TEXT_MATCH.replace("Gross Wt (kgs): 22,000 KG", "Gross Wt (kgs): N/A")

INVOICE_TEXT = """COMMERCIAL INVOICE
Invoice No.: 123
*** THIS IS A COMMERCIAL INVOICE - NOT A SHIPPING INSTRUCTION ***
"""


def test_missing_attachment_when_bl_absent():
    si = parse_txt_document(SI_TEXT, role="SI")
    result = decide(si, None)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.review_reason.value == "missing_attachment"


def test_wrong_doc_type_when_bl_is_invoice():
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(INVOICE_TEXT, role="BL")
    result = decide(si, bl)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.review_reason.value == "wrong_doc_type"


def test_unreadable_when_doc_kind_unknown():
    from core.models import DocumentExtraction

    si = parse_txt_document(SI_TEXT, role="SI")
    bl = DocumentExtraction(role="BL", doc_kind="UNKNOWN", readable=False)
    result = decide(si, bl)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.review_reason.value == "unreadable"


def test_missing_value_when_field_blank():
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(BL_TEXT_MISSING_WEIGHT, role="BL")
    result = decide(si, bl)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.review_reason.value == "missing_value"


def test_mismatch_flags_exact_defect_field():
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(BL_TEXT_MISMATCH_CONTAINERS, role="BL")
    result = decide(si, bl)
    assert result.status.value == "MISMATCH"
    assert result.has_defect is True
    assert result.defect_fields == ["container_count"]


def test_ok_when_all_seven_fields_match():
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(BL_TEXT_MATCH, role="BL")
    result = decide(si, bl)
    assert result.status.value == "OK"
    assert result.has_defect is False
    assert result.defect_fields == []
