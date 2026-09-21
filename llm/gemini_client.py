"""Gemini extraction client: structured JSON output, evidence validation,
sha256-keyed caching. The LLM never decides OK/MISMATCH/NEEDS_REVIEW — it only
extracts field values with evidence; core/decide.py makes the deterministic call."""
import hashlib
import json
import random
import time
from pathlib import Path

from google import genai
from google.genai import types

from config import settings
from core.extract_rules import detect_doc_kind
from core.models import COMPARED_FIELDS, DecidedBy, DocumentExtraction, ExtractedField, FieldState
from llm.prompts import PROMPT_VERSION, SYSTEM_INSTRUCTION, build_text_extraction_prompt, build_vision_extraction_prompt
from llm.schemas import GeminiExtraction
from llm.validate import evidence_supports_value

CACHE_DIR = Path("gemini_cache")
MAX_RETRIES = 3


def _client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def _cache_key(payload_bytes: bytes, kind: str) -> str:
    h = hashlib.sha256()
    h.update(payload_bytes)
    h.update(PROMPT_VERSION.encode())
    h.update(settings.gemini_model.encode())
    h.update(kind.encode())
    return h.hexdigest()


def _cache_get(key: str) -> dict | None:
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _cache_put(key: str, value: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(value), encoding="utf-8")


def _client_error_status(exc: Exception) -> int | None:
    """Best-effort extraction of an HTTP status code from an SDK exception,
    without depending on a specific google-genai exception class."""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return status
    return None


def _call_with_retries(fn):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - external API, broad catch is intentional
            status = _client_error_status(e)
            if status is not None and 400 <= status < 500:
                raise  # auth/bad-request errors won't fix themselves on retry
            last_err = e
            time.sleep(1.5 * (attempt + 1) + random.uniform(0, 0.5))
    raise last_err


def _generate_structured(contents: list) -> GeminiExtraction:
    client = _client()

    def call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0,
                response_mime_type="application/json",
                response_schema=GeminiExtraction,
            ),
        )

    resp = _call_with_retries(call)
    return GeminiExtraction.model_validate_json(resp.text)


def _cross_checked_doc_kind(claimed_kind: str, source_text: str | None) -> str:
    """Gemini's doc_kind is untrusted (it's derived from document content it
    was told may contain injected instructions). Where the text has a
    deterministic, non-LLM header signal, require it to agree; a specific
    disagreement is treated as "we don't actually know" rather than trusting
    the LLM's say-so."""
    if source_text is None:
        return claimed_kind
    deterministic_kind = detect_doc_kind(source_text)
    if deterministic_kind not in ("OTHER", "UNKNOWN") and deterministic_kind != claimed_kind:
        return "UNKNOWN"
    return claimed_kind


def _build_document_extraction(
    extraction: GeminiExtraction, role: str, filename: str, source_text: str | None
) -> DocumentExtraction:
    fields: dict[str, ExtractedField] = {}
    for field in COMPARED_FIELDS:
        fv = getattr(extraction, field)
        if fv.value is None:
            continue
        if source_text is not None:
            if not evidence_supports_value(source_text, fv.evidence, fv.value, field=field):
                continue  # discard low-confidence / unvalidated field
        fields[field] = ExtractedField(
            field=field,
            source_label=fv.source_label,
            raw_value=fv.value,
            state=FieldState.VALUE,
            method=DecidedBy.GEMINI,
            confidence=0.9,
            evidence_quote=fv.evidence,
        )
    doc_kind = extraction.doc_kind if extraction.readable else "UNKNOWN"
    doc_kind = _cross_checked_doc_kind(doc_kind, source_text)
    return DocumentExtraction(
        role=role,
        filename=filename,
        doc_kind=doc_kind,
        readable=extraction.readable,
        fields=fields,
        raw_text=source_text,
    )


def extract_from_text(document_bytes: bytes, document_text: str, role: str, filename: str) -> DocumentExtraction:
    key = _cache_key(document_bytes, "text")
    cached = _cache_get(key)
    if cached is not None:
        extraction = GeminiExtraction.model_validate(cached)
    else:
        prompt = build_text_extraction_prompt(document_text, role)
        extraction = _generate_structured([prompt])
        _cache_put(key, extraction.model_dump())
    return _build_document_extraction(extraction, role, filename, document_text)


def extract_from_images(document_bytes: bytes, images: list[bytes], role: str, filename: str) -> DocumentExtraction:
    """Scanned/image-only documents: two independent Gemini vision reads must
    agree on a field before it is trusted (no text source to validate evidence
    against, so cross-run agreement is the substitute check)."""
    key = _cache_key(document_bytes, "vision")
    cached = _cache_get(key)
    if cached is not None:
        pair = cached
    else:
        prompt = build_vision_extraction_prompt(role)
        parts = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        run1 = _generate_structured([prompt, *parts])
        run2 = _generate_structured([prompt, *parts])
        pair = [run1.model_dump(), run2.model_dump()]
        _cache_put(key, pair)

    run1 = GeminiExtraction.model_validate(pair[0])
    run2 = GeminiExtraction.model_validate(pair[1])

    if not run1.readable or not run2.readable:
        return DocumentExtraction(role=role, filename=filename, doc_kind="UNKNOWN", readable=False)

    fields: dict[str, ExtractedField] = {}
    for field in COMPARED_FIELDS:
        v1, v2 = getattr(run1, field), getattr(run2, field)
        if v1.value is not None and v1.value == v2.value:
            fields[field] = ExtractedField(
                field=field,
                source_label=v1.source_label,
                raw_value=v1.value,
                state=FieldState.VALUE,
                method=DecidedBy.GEMINI,
                confidence=0.85,
                evidence_quote=v1.evidence,
            )

    doc_kind = run1.doc_kind if run1.doc_kind == run2.doc_kind else "UNKNOWN"
    return DocumentExtraction(
        role=role,
        filename=filename,
        doc_kind=doc_kind,
        readable=True,
        fields=fields,
    )
