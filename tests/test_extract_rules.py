from core.extract_rules import detect_doc_kind, parse_txt_document

SI_TEXT = """SHIPPING INSTRUCTION
========================================

Shipper/Exporter: APRIL FAR EAST (M) SDN BHD
  TOWER 2, AVENUE 5, LEVEL 6
CONSIGNEE: MOORIM SP CO., LTD
NOTIFY PARTY: UAB NOVAKOPA
Port of Loading: PORT KLANG (WESTPORT), MALAYSIA (MYPKG)
Discharge Port: CALLAO, PERU (PECLL)
No. of Containers or Packages: 1 x 40'HC
Gross Weight (KG): 21,577 KG
"""

BL_TEXT = """BILL OF LADING (DRAFT)
========================================

SHIPPER: APRIL FAR EAST (M) SDN BHD
CONSIGNEE: MOORIM SP CO., LTD
Notify: UAB NOVAKOPA
Port of Loading (POL): PORT KLANG (WESTPORT), MALAYSIA (MYPKG)
POD: CALLAO, PERU (PECLL)
Container Count: 1 x 40'HC
Gross Wt (kgs): 21,577 KG
"""

INVOICE_TEXT = """COMMERCIAL INVOICE
========================================

Invoice No.: 5250078266
Seller: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE

*** THIS IS A COMMERCIAL INVOICE - NOT A SHIPPING INSTRUCTION ***
"""


def test_doc_kind_si_and_bl():
    assert detect_doc_kind(SI_TEXT) == "SI"
    assert detect_doc_kind(BL_TEXT) == "BL"


def test_doc_kind_commercial_invoice_with_banner():
    assert detect_doc_kind(INVOICE_TEXT) == "COMMERCIAL_INVOICE"


def test_doc_kind_si_with_corroborating_not_a_bl_banner_stays_si():
    text = (
        "SHIPPING INSTRUCTION\n"
        "========================================\n"
        "*** THIS IS A SHIPPING INSTRUCTION - NOT A BILL OF LADING ***\n"
        "Shipper: A CO\n"
    )
    assert detect_doc_kind(text) == "SI"


def test_doc_kind_skips_letterhead_and_decorative_rule_lines():
    text = (
        "=====================================\n"
        "APRIL FAR EAST (M) SDN BHD\n"
        "-------------------------------------\n"
        "SHIPPING INSTRUCTION\n"
        "Shipper: A CO\n"
    )
    assert detect_doc_kind(text) == "SI"


def test_doc_kind_prefers_bill_of_lading_when_both_needles_in_header_line():
    text = "BILL OF LADING - DRAFT (per SHIPPING INSTRUCTION 42)\nShipper: A CO\n"
    assert detect_doc_kind(text) == "BL"


def test_parse_si_aliases_map_to_canonical_fields():
    doc = parse_txt_document(SI_TEXT, role="SI")
    assert doc.doc_kind == "SI"
    assert doc.fields["shipper"].raw_value == "APRIL FAR EAST (M) SDN BHD"
    assert doc.fields["consignee"].raw_value == "MOORIM SP CO., LTD"
    assert doc.fields["notify_party"].raw_value == "UAB NOVAKOPA"
    assert doc.fields["port_of_loading"].raw_value == "PORT KLANG (WESTPORT), MALAYSIA (MYPKG)"
    assert doc.fields["port_of_discharge"].raw_value == "CALLAO, PERU (PECLL)"
    assert doc.fields["container_count"].raw_value == "1 x 40'HC"
    assert doc.fields["gross_weight_kg"].raw_value == "21,577 KG"


def test_parse_bl_uses_different_labels_same_canonical_fields():
    doc = parse_txt_document(BL_TEXT, role="BL")
    assert set(doc.fields.keys()) == {
        "shipper", "consignee", "notify_party",
        "port_of_loading", "port_of_discharge",
        "container_count", "gross_weight_kg",
    }


def test_blank_value_marks_field_state_blank():
    text = "SHIPPING INSTRUCTION\nGross Weight (KG): N/A\n"
    doc = parse_txt_document(text, role="SI")
    assert doc.fields["gross_weight_kg"].state.value == "blank"
    assert doc.fields["gross_weight_kg"].raw_value is None


def test_net_weight_does_not_pollute_gross_weight():
    text = "SHIPPING INSTRUCTION\nGross Weight (KG): 100 KG\nNET WEIGHT: 90 KG\n"
    doc = parse_txt_document(text, role="SI")
    assert doc.fields["gross_weight_kg"].raw_value == "100 KG"
    assert "net_weight" not in doc.fields


def test_container_number_label_does_not_hijack_container_count():
    text = "SHIPPING INSTRUCTION\nContainer No.: MSKU1234567\n"
    doc = parse_txt_document(text, role="SI")
    assert "container_count" not in doc.fields


def test_date_of_loading_label_does_not_hijack_port_of_loading():
    text = "SHIPPING INSTRUCTION\nDate of Loading: 2026-05-01\n"
    doc = parse_txt_document(text, role="SI")
    assert "port_of_loading" not in doc.fields


def test_shipper_ref_label_does_not_hijack_shipper():
    text = "SHIPPING INSTRUCTION\nShipper Ref: REF-0042\n"
    doc = parse_txt_document(text, role="SI")
    assert "shipper" not in doc.fields


def test_free_text_with_incidental_colon_does_not_hijack_notify_party():
    text = "SHIPPING INSTRUCTION\nPlease notify the consignee at 10:30 on arrival\n"
    doc = parse_txt_document(text, role="SI")
    assert "notify_party" not in doc.fields


def test_conflicting_duplicate_labels_flag_field_instead_of_keeping_first():
    text = "SHIPPING INSTRUCTION\nShipper: A CO\nShipper/Exporter: B CO\n"
    doc = parse_txt_document(text, role="SI")
    assert doc.fields["shipper"].state.value == "blank"
    assert doc.fields["shipper"].raw_value is None


def test_identical_duplicate_labels_do_not_flag_field():
    text = "SHIPPING INSTRUCTION\nShipper: A CO\nShipper/Exporter: A CO\n"
    doc = parse_txt_document(text, role="SI")
    assert doc.fields["shipper"].raw_value == "A CO"
    assert doc.fields["shipper"].state.value == "value"
