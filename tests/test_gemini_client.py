import pytest

from llm.gemini_client import _call_with_retries


class _FakeApiError(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def test_call_with_retries_does_not_retry_on_client_error():
    calls = []

    def fn():
        calls.append(1)
        raise _FakeApiError(401)

    with pytest.raises(_FakeApiError):
        _call_with_retries(fn)

    assert len(calls) == 1


def test_call_with_retries_retries_on_server_error(monkeypatch):
    monkeypatch.setattr("llm.gemini_client.time.sleep", lambda *_: None)
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _FakeApiError(503)
        return "ok"

    assert _call_with_retries(fn) == "ok"
    assert len(calls) == 3


def test_call_with_retries_retries_on_unknown_error(monkeypatch):
    monkeypatch.setattr("llm.gemini_client.time.sleep", lambda *_: None)
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient network blip")
        return "ok"

    assert _call_with_retries(fn) == "ok"
    assert len(calls) == 2
