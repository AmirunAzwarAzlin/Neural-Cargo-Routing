import json

from core.models import COMPARED_FIELDS
from llm.gemini_client import _cache_dir, _cache_key, extract_from_images
from llm.schemas import GeminiExtraction


def _extraction(doc_kind="SI", readable=True, **field_values):
    data = {"doc_kind": doc_kind, "readable": readable}
    for field in COMPARED_FIELDS:
        data[field] = {"value": None, "evidence": None, "source_label": None}
    for field, (value, evidence) in field_values.items():
        data[field] = {"value": value, "evidence": evidence, "source_label": None}
    return GeminiExtraction.model_validate(data)


def test_cache_key_differs_by_role():
    # Same bytes attached in the SI slot vs the BL slot must not reuse the
    # first result — the prompt itself includes the role.
    key_si = _cache_key(b"same-bytes", "vision", "SI")
    key_bl = _cache_key(b"same-bytes", "vision", "BL")
    assert key_si != key_bl


def test_cache_key_same_inputs_are_stable():
    assert _cache_key(b"x", "text", "SI") == _cache_key(b"x", "text", "SI")


def test_cache_dir_falls_back_to_tempdir_when_primary_is_unwritable(monkeypatch, tmp_path):
    import llm.gemini_client as gc

    unwritable = tmp_path / "readonly_parent" / "gemini_cache"
    monkeypatch.setattr(gc, "CACHE_DIR", unwritable)

    def fake_mkdir(self, *args, **kwargs):
        if self == unwritable:
            raise OSError("read-only filesystem")
        return None

    monkeypatch.setattr(type(unwritable), "mkdir", fake_mkdir, raising=False)

    result = _cache_dir()
    assert result != unwritable


def test_vision_extraction_tolerates_whitespace_differences_between_runs(monkeypatch, tmp_path):
    import llm.gemini_client as gc

    monkeypatch.setattr(gc, "CACHE_DIR", tmp_path / "cache")
    calls = []

    def fake_generate_structured(contents, temperature=0):
        calls.append(temperature)
        if len(calls) == 1:
            return _extraction(shipper=("A CO", "Shipper: A CO"))
        return _extraction(shipper=("A CO  ", "Shipper: A CO  "))  # trailing whitespace only

    monkeypatch.setattr(gc, "_generate_structured", fake_generate_structured)

    result = extract_from_images(b"imgbytes", [b"page1"], "SI", "att.pdf")

    assert result.fields["shipper"].raw_value == "A CO"


def test_vision_extraction_uses_a_different_temperature_for_the_second_read(monkeypatch, tmp_path):
    import llm.gemini_client as gc

    monkeypatch.setattr(gc, "CACHE_DIR", tmp_path / "cache")
    temperatures = []

    def fake_generate_structured(contents, temperature=0):
        temperatures.append(temperature)
        return _extraction()

    monkeypatch.setattr(gc, "_generate_structured", fake_generate_structured)

    extract_from_images(b"imgbytes", [b"page1"], "SI", "att.pdf")

    assert len(temperatures) == 2
    assert temperatures[0] != temperatures[1]
