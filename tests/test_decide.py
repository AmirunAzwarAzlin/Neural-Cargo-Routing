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

SI_TEXT_UNPARSEABLE = SI_TEXT.replace(
    "No. of Containers: 3 x 40'HC", "No. of Containers: FCL"
).replace("Gross Weight (KG): 22,000 KG", "Gross Weight (KG): AS PER LIST")

BL_TEXT_UNPARSEABLE = BL_TEXT_MATCH.replace(
    "Container Count: 3 x 40'HC", "Container Count: LCL"
).replace("Gross Wt (kgs): 22,000 KG", "Gross Wt (kgs): TBC")

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


def test_missing_value_surfaces_a_known_mismatch_hidden_by_the_blank_field():
    # A blank weight forces NEEDS_REVIEW/missing_value (has_defect stays
    # false per the competition's submission.json shape), but a real
    # consignee defect elsewhere must not become invisible outside per_field.
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(
        BL_TEXT_MISSING_WEIGHT.replace("Consignee: B CO", "Consignee: EVIL CO"), role="BL"
    )
    result = decide(si, bl)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.has_defect is False
    assert result.defect_fields == []
    assert "consignee" in result.notes


def test_mismatch_detects_multi_type_container_count_change():
    si = parse_txt_document(SI_TEXT.replace("3 x 40'HC", "1 x 40'HC + 2 x 20'GP"), role="SI")
    bl = parse_txt_document(BL_TEXT_MATCH.replace("3 x 40'HC", "1 x 40'HC + 5 x 20'GP"), role="BL")
    result = decide(si, bl)
    assert result.status.value == "MISMATCH"
    assert result.defect_fields == ["container_count"]


def test_mismatch_flags_exact_defect_field():
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(BL_TEXT_MISMATCH_CONTAINERS, role="BL")
    result = decide(si, bl)
    assert result.status.value == "MISMATCH"
    assert result.has_defect is True
    assert result.defect_fields == ["container_count"]


def test_unparseable_values_on_both_sides_do_not_silently_match():
    si = parse_txt_document(SI_TEXT_UNPARSEABLE, role="SI")
    bl = parse_txt_document(BL_TEXT_UNPARSEABLE, role="BL")
    result = decide(si, bl)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.review_reason.value == "missing_value"


def test_mismatch_detects_port_unlocode_only_change():
    si = parse_txt_document(SI_TEXT.replace("Port of Loading: SINGAPORE", "Port of Loading: SHANGHAI (CNSHA)"), role="SI")
    bl = parse_txt_document(BL_TEXT_MATCH.replace("Port of Loading: SINGAPORE", "Port of Loading: SHANGHAI (CNSGH)"), role="BL")
    result = decide(si, bl)
    assert result.status.value == "MISMATCH"
    assert result.defect_fields == ["port_of_loading"]


def test_ok_when_all_seven_fields_match():
    si = parse_txt_document(SI_TEXT, role="SI")
    bl = parse_txt_document(BL_TEXT_MATCH, role="BL")
    result = decide(si, bl)
    assert result.status.value == "OK"
    assert result.has_defect is False
    assert result.defect_fields == []
