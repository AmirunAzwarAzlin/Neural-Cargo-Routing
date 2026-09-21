from llm.validate import evidence_supports_value


def test_evidence_supports_value_when_present_verbatim():
    source = "SHIPPING INSTRUCTION\nGross Weight (KG): 21,577 KG\n"
    assert evidence_supports_value(source, "Gross Weight (KG): 21,577 KG", "21,577 KG")


def test_evidence_supports_value_case_and_whitespace_insensitive():
    source = "Shipper:   TEST   CO\n"
    assert evidence_supports_value(source, "shipper: test co", "TEST CO")


def test_evidence_rejects_hallucinated_evidence_not_in_source():
    source = "SHIPPING INSTRUCTION\nGross Weight (KG): 21,577 KG\n"
    assert not evidence_supports_value(source, "Gross Weight (KG): 99,999 KG", "99,999 KG")


def test_evidence_rejects_value_not_actually_in_evidence_quote():
    source = "Gross Weight (KG): 21,577 KG\n"
    assert not evidence_supports_value(source, "Gross Weight (KG): 21,577 KG", "50,000 KG")


def test_evidence_rejects_missing_evidence_or_value():
    assert not evidence_supports_value("some text", None, "value")
    assert not evidence_supports_value("some text", "evidence", None)


def test_evidence_rejects_truncated_value_that_is_merely_a_substring():
    source = "Shipper: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE\n"
    evidence = "Shipper: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert not evidence_supports_value(source, evidence, "APRIL")


def test_evidence_accepts_exact_value_after_stripping_label():
    source = "Shipper: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE\n"
    evidence = "Shipper: APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"
    assert evidence_supports_value(source, evidence, "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE")


def test_evidence_rejects_a_different_fields_label():
    source = "Consignee: XYZ SDN BHD\n"
    evidence = "Consignee: XYZ SDN BHD"
    assert not evidence_supports_value(source, evidence, "XYZ SDN BHD", field="notify_party")


def test_evidence_accepts_the_matching_fields_own_label():
    source = "Consignee: XYZ SDN BHD\n"
    evidence = "Consignee: XYZ SDN BHD"
    assert evidence_supports_value(source, evidence, "XYZ SDN BHD", field="consignee")
