from core.decide import decide
from core.extract_rules import parse_txt_document
from core.models import Category, DecidedBy, EmailResult
from storage.supabase_store import persist_email_result
from tests.fakes import FakeClient

SI_TEXT = """SHIPPING INSTRUCTION
Shipper: A CO
Consignee: B CO
Notify Party: C CO
Port of Loading: SINGAPORE
Discharge Port: TOKYO, JAPAN
No. of Containers: 3 x 40'HC
Gross Weight (KG): 22,000 KG
"""

BL_TEXT = """BILL OF LADING (DRAFT)
Shipper: A CO
Consignee: B CO
Notify: C CO
Port of Loading: SINGAPORE
POD: TOKYO, JAPAN
Container Count: 3 x 40'HC
Gross Wt (kgs): 22,000 KG
"""


def _build_result() -> EmailResult:
    si = parse_txt_document(SI_TEXT, role="SI", filename="e1_SI.txt")
    bl = parse_txt_document(BL_TEXT, role="BL", filename="e1_BL.txt")
    result = EmailResult(
        email_id="email_001",
        category=Category.BL_COMPARISON,
        category_decided_by=DecidedBy.RULE,
        category_rationale="has SI/BL attachment",
    )
    result.si_doc = si
    result.bl_doc = bl
    result.comparison = decide(si, bl)
    return result


def test_persisting_the_same_email_twice_does_not_duplicate_rows():
    client = FakeClient()
    email = {"email_id": "email_001", "from": "a@x.com", "subject": "s", "body": "b", "attachments": []}
    result = _build_result()

    persist_email_result(client, None, email, result, {})
    persist_email_result(client, None, email, result, {})

    assert len(client.table("classifications").rows) == 1
    assert len(client.table("documents").rows) == 2  # SI + BL, not 4
    assert len(client.table("extracted_fields").rows) == 14  # 7 fields x 2 docs, not 28
    assert len(client.table("comparisons").rows) == 1


def test_persisting_the_same_email_twice_updates_not_appends_field_values():
    client = FakeClient()
    email = {"email_id": "email_001", "from": "a@x.com", "subject": "s", "body": "b", "attachments": []}
    result = _build_result()

    persist_email_result(client, None, email, result, {})
    result.si_doc.fields["shipper"].raw_value = "CHANGED CO"
    persist_email_result(client, None, email, result, {})

    si_doc_id = next(r["id"] for r in client.table("documents").rows if r["role"] == "SI")
    shipper_rows = [
        r for r in client.table("extracted_fields").rows
        if r["field"] == "shipper" and r["document_id"] == si_doc_id
    ]
    assert len(shipper_rows) == 1
    assert shipper_rows[0]["raw_value"] == "CHANGED CO"
