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
