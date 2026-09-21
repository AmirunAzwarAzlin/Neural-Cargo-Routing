from app import queries
from tests.fakes import FakeClient


def test_get_email_detail_does_not_raise_for_unknown_email_id():
    client = FakeClient()

    detail = queries.get_email_detail(client, "no-such-email")

    assert detail["email"] is None
    assert detail["documents"] == []


def test_get_email_detail_returns_the_matching_email_row():
    client = FakeClient()
    client.table("emails").rows.append({"email_id": "email_A", "subject": "hi"})

    detail = queries.get_email_detail(client, "email_A")

    assert detail["email"]["subject"] == "hi"
