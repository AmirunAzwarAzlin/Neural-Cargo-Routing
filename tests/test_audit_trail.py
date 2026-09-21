import pytest

from app import queries
from tests.fakes import FakeClient


def _seed_document(client: FakeClient, email_id: str, role: str = "SI") -> str:
    row = client.table("documents").insert({
        "email_id": email_id, "role": role, "doc_kind": role, "readable": True,
    }).execute().data[0]
    return row["id"]


def test_correct_field_rejects_unknown_field_name():
    client = FakeClient()
    doc_id = _seed_document(client, "email_A")

    with pytest.raises(ValueError):
        queries.correct_field(client, "email_A", doc_id, "not_a_real_field; DROP TABLE x", "value")


def test_correct_field_rejects_value_over_length_cap():
    client = FakeClient()
    doc_id = _seed_document(client, "email_A")

    with pytest.raises(ValueError):
        queries.correct_field(client, "email_A", doc_id, "shipper", "x" * 100_000)


def test_correct_field_rejects_document_from_a_different_email():
    client = FakeClient()
    doc_id = _seed_document(client, "email_A")

    with pytest.raises(ValueError):
        queries.correct_field(client, "email_B", doc_id, "shipper", "NEW CO")


def test_correct_field_returns_the_previous_value():
    client = FakeClient()
    doc_id = _seed_document(client, "email_A")
    client.table("extracted_fields").insert({
        "document_id": doc_id, "field": "shipper", "raw_value": "OLD CO",
        "state": "value", "method": "rule", "confidence": 1.0,
    }).execute()

    old_value = queries.correct_field(client, "email_A", doc_id, "shipper", "NEW CO")

    assert old_value == "OLD CO"


def test_correct_doc_rejects_document_from_a_different_email():
    client = FakeClient()
    doc_id = _seed_document(client, "email_A")

    with pytest.raises(ValueError):
        queries.correct_doc(client, "email_B", doc_id, doc_kind="SI", readable=True)


def test_correct_doc_rejects_unknown_doc_kind():
    client = FakeClient()
    doc_id = _seed_document(client, "email_A")

    with pytest.raises(ValueError):
        queries.correct_doc(client, "email_A", doc_id, doc_kind="NOT_A_KIND", readable=True)
