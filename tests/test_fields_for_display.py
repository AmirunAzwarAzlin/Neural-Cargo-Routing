from app.queries import fields_for_display
from core.models import COMPARED_FIELDS


def test_fields_for_display_includes_every_compared_field():
    rows = [{"field": "shipper", "raw_value": "A CO", "state": "value"}]

    result = fields_for_display(rows)

    assert [r["field"] for r in result] == COMPARED_FIELDS


def test_fields_for_display_marks_missing_fields_absent():
    rows = [{"field": "shipper", "raw_value": "A CO", "state": "value"}]

    result = fields_for_display(rows)

    consignee = next(r for r in result if r["field"] == "consignee")
    assert consignee["raw_value"] is None
    assert consignee["state"] == "absent"


def test_fields_for_display_preserves_existing_row_data():
    rows = [{"field": "shipper", "raw_value": "A CO", "state": "value", "method": "rule"}]

    result = fields_for_display(rows)

    shipper = next(r for r in result if r["field"] == "shipper")
    assert shipper["raw_value"] == "A CO"
    assert shipper["method"] == "rule"
