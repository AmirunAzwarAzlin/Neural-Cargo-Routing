from app import queries
from storage.supabase_store import fetch_all
from tests.fakes import FakeClient


def test_fetch_all_pages_past_the_row_cap():
    client = FakeClient()
    table = client.table("extracted_fields")
    for i in range(25):
        table.rows.append({"id": f"row-{i}", "field": "shipper"})

    rows = fetch_all(lambda: client.table("extracted_fields").select("*"), page_size=10)

    assert len(rows) == 25
    assert {r["id"] for r in rows} == {f"row-{i}" for i in range(25)}


def test_fetch_all_single_page_when_under_cap():
    client = FakeClient()
    table = client.table("extracted_fields")
    for i in range(3):
        table.rows.append({"id": f"row-{i}"})

    rows = fetch_all(lambda: client.table("extracted_fields").select("*"), page_size=10)

    assert len(rows) == 3


def test_dashboard_summary_counts_past_the_row_cap(monkeypatch):
    monkeypatch.setattr("app.queries.PAGE_SIZE", 10)
    client = FakeClient()
    for i in range(25):
        client.table("classifications").rows.append(
            {"email_id": f"e{i}", "category": "GENERAL", "decided_by": "rule"}
        )
    for i in range(25):
        client.table("comparisons").rows.append(
            {"email_id": f"e{i}", "status": "OK", "review_reason": None, "defect_fields": []}
        )
    for i in range(1500):
        client.table("extracted_fields").rows.append({"id": f"f{i}", "field": "shipper", "method": "rule"})

    summary = queries.dashboard_summary(client)

    assert summary["total_emails"] == 25
    assert summary["field_extraction_methods"]["rule"] == 1500
