from app import queries
from tests.fakes import FakeClient

FIELDS = [
    ("shipper", "A CO"),
    ("consignee", "B CO"),
    ("notify_party", "C CO"),
    ("port_of_loading", "SINGAPORE"),
    ("port_of_discharge", "TOKYO"),
    ("container_count", "3 x 40'HC"),
    ("gross_weight_kg", "22,000 KG"),
]


def _seed_comparable_email(client: FakeClient, email_id: str, si_kwargs=None, bl_kwargs=None) -> tuple[str, str]:
    si_kwargs = si_kwargs or {}
    bl_kwargs = bl_kwargs or {}
    si_row = client.table("documents").insert({
        "email_id": email_id, "role": "SI", "filename": "si.txt",
        "doc_kind": si_kwargs.get("doc_kind", "SI"), "readable": si_kwargs.get("readable", True),
        "doc_kind_method": "rule",
    }).execute().data[0]
    bl_row = client.table("documents").insert({
        "email_id": email_id, "role": "BL", "filename": "bl.txt",
        "doc_kind": bl_kwargs.get("doc_kind", "BL"), "readable": bl_kwargs.get("readable", True),
        "doc_kind_method": "rule",
    }).execute().data[0]
    for field, value in FIELDS:
        client.table("extracted_fields").insert({
            "document_id": si_row["id"], "field": field, "source_label": field,
            "raw_value": value, "normalized_value": None, "state": "value",
            "method": "rule", "confidence": 1.0, "evidence_quote": None,
        }).execute()
        client.table("extracted_fields").insert({
            "document_id": bl_row["id"], "field": field, "source_label": field,
            "raw_value": value, "normalized_value": None, "state": "value",
            "method": "rule", "confidence": 1.0, "evidence_quote": None,
        }).execute()
    client.table("comparisons").insert({
        "email_id": email_id, "status": "NEEDS_REVIEW", "review_reason": "missing_value",
        "has_defect": False, "defect_fields": [], "per_field": [],
        "decided_by": "rule", "rules_version": "v1", "notes": None,
        "review_status": "pending", "reviewed_by": None, "reviewed_at": None,
    }).execute()
    return si_row["id"], bl_row["id"]


def test_confirm_does_not_overwrite_the_comparison_verdict():
    client = FakeClient()
    _seed_comparable_email(client, "email_A")

    queries.apply_review_action(client, "email_A", actor="alice", action="confirm", field=None, reason="")

    row = client.table("comparisons").rows[0]
    assert row["status"] == "NEEDS_REVIEW"  # untouched, not silently recomputed
    assert row["review_status"] == "confirmed"
    assert row["reviewed_by"] == "alice"
    assert row["reviewed_at"] is not None


def test_reject_records_review_status_without_recomputing():
    client = FakeClient()
    _seed_comparable_email(client, "email_A")

    queries.apply_review_action(client, "email_A", actor="bob", action="reject", field=None, reason="bad scan")

    row = client.table("comparisons").rows[0]
    assert row["status"] == "NEEDS_REVIEW"
    assert row["review_status"] == "rejected"
    assert row["reviewed_by"] == "bob"


def test_correcting_a_field_recomputes_and_marks_decided_by_human():
    client = FakeClient()
    _seed_comparable_email(client, "email_A")

    queries.apply_review_action(client, "email_A", actor="alice", action="correct", field="shipper", reason="")

    row = client.table("comparisons").rows[0]
    assert row["status"] == "OK"  # all 7 fields now match -> resolved
    assert row["decided_by"] == "human"


def test_correct_doc_lets_human_override_unreadable_and_decide_honours_it():
    client = FakeClient()
    _seed_comparable_email(client, "email_A", si_kwargs={"doc_kind": "UNKNOWN", "readable": False})
    si_doc_id = next(r["id"] for r in client.table("documents").rows if r["role"] == "SI")

    queries.correct_doc(client, "email_A", si_doc_id, doc_kind="SI", readable=True)
    result = queries.apply_review_action(client, "email_A", actor="alice", action="correct", field="doc_kind", reason="")

    assert result["status"] == "OK"
    doc_row = next(r for r in client.table("documents").rows if r["id"] == si_doc_id)
    assert doc_row["doc_kind_method"] == "human"


def test_confirm_and_reject_still_write_an_audit_row():
    client = FakeClient()
    _seed_comparable_email(client, "email_A")

    queries.apply_review_action(client, "email_A", actor="alice", action="confirm", field=None, reason="looks fine")

    actions = client.table("review_actions").rows
    assert len(actions) == 1
    assert actions[0]["action"] == "confirm"
    assert actions[0]["actor"] == "alice"
