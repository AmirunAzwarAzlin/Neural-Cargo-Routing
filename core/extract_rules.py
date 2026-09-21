"""Deterministic rule-based extraction for plain-text SI/BL attachments.

Alias table built by reading data/attachments/*.txt by hand (Phase 0), never
from an answer key. See README Decisions log for the label survey.
"""
import re

from core.models import DocumentExtraction, ExtractedField, FieldState

BLANK_VALUES = {"", "n/a", "na", "tba", "-", "none", "null"}

LINE_RE = re.compile(r"^\s*(.+?)\s*[:：]\s*(.*)$")

# canonical field -> normalized (lowercase, punctuation-stripped) exact label aliases
FIELD_ALIASES: dict[str, set[str]] = {
    "shipper": {
        "shipper",
        "shipper exporter",
        "shipper principal or seller",
    },
    "consignee": {
        "consignee",
        "consignee non negotiable",
        "to the order of",
    },
    "notify_party": {
        "notify",
        "notify party",
        "notify party intermediate consignee",
    },
    "port_of_loading": {
        "port of loading",
        "port of loading pol",
        "load port",
        "pol",
    },
    "port_of_discharge": {
        "discharge port",
        "port of discharge",
        "port of discharge pod",
        "pod",
    },
    "container_count": {
        "no of containers",
        "no of containers or packages",
        "total containers",
        "container count",
    },
    "gross_weight_kg": {
        "gross weight kg",
        "gross wt kgs",
        "gross weight",
    },
}

# doc_kind detection: header line -> kind, plus explicit banner corroboration.
HEADER_KIND_MAP = [
    ("SHIPPING INSTRUCTION", "SI"),
    ("BILL OF LADING", "BL"),
    ("COMMERCIAL INVOICE", "COMMERCIAL_INVOICE"),
    ("CERTIFICATE OF ORIGIN", "CERT_OF_ORIGIN"),
    ("PACKING LIST", "PACKING_LIST"),
]


def _normalize_label(label: str) -> str:
    label = label.strip().lower()
    # drop a bracketed UNLOCODE-style or Chinese suffix e.g. "gross weight毛重(kgs)"
    label = re.sub(r"[^\x00-\x7f]", "", label)
    label = re.sub(r"[^a-z0-9]+", " ", label)
    return label.strip()


def _canonical_field_for_label(label: str) -> str | None:
    """Only an exact (normalized) match against FIELD_ALIASES counts.

    A broad substring fallback used to live here, but it hijacked unrelated
    labels ("Container No.", "Date of Loading", "Shipper Ref") and even
    free-text sentences containing an incidental colon (e.g. a timestamp).
    When a label doesn't exactly match a known alias, the field is left
    unextracted so the system escalates instead of guessing.
    """
    norm = _normalize_label(label)
    if not norm:
        return None
    for field, aliases in FIELD_ALIASES.items():
        if norm in aliases:
            return field
    return None


_DECORATIVE_CHARS = set("=-*_# \t")
_MAX_HEADER_CANDIDATE_LINES = 10


def _match_kind_in_line(line: str) -> str | None:
    """Pick the needle that occurs earliest in the line (ties broken by the
    longer/more specific needle), not the first one listed in HEADER_KIND_MAP.
    This also resolves headers like "BILL OF LADING - DRAFT (per SHIPPING
    INSTRUCTION 42)" correctly in favour of the earlier-occurring BL needle.
    """
    best_pos, best_len, best_mapped = None, -1, None
    for needle, mapped in HEADER_KIND_MAP:
        idx = line.find(needle)
        if idx == -1:
            continue
        if best_pos is None or idx < best_pos or (idx == best_pos and len(needle) > best_len):
            best_pos, best_len, best_mapped = idx, len(needle), mapped
    return best_mapped


def _banner_named_kind(text: str) -> str | None:
    """What kind (if any) a "*** ... NOT A <KIND> ... ***" banner disclaims."""
    m = re.search(r"\*{2,}.*?NOT\s+(?:A|AN)\s+(.+?)\s*\*{2,}", text, re.IGNORECASE)
    if not m:
        return None
    named = m.group(1).strip().upper()
    return _match_kind_in_line(named)


def detect_doc_kind(text: str) -> str:
    candidate_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or set(stripped) <= _DECORATIVE_CHARS:
            continue
        candidate_lines.append(stripped.upper())
        if len(candidate_lines) >= _MAX_HEADER_CANDIDATE_LINES:
            break

    kind = "OTHER"
    for line in candidate_lines:
        matched = _match_kind_in_line(line)
        if matched:
            kind = matched
            break

    banner_kind = _banner_named_kind(text)
    if banner_kind is not None and banner_kind == kind:
        # header claimed this kind but the body explicitly disclaims it
        kind = "OTHER"
    return kind


def parse_txt_document(text: str, role: str, filename: str | None = None) -> DocumentExtraction:
    doc_kind = detect_doc_kind(text)
    fields: dict[str, ExtractedField] = {}
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        label, raw_value = m.group(1), m.group(2)
        field = _canonical_field_for_label(label)
        if field is None:
            continue
        raw_value = raw_value.strip()
        value_norm_check = raw_value.strip("_ ").lower()
        if value_norm_check in BLANK_VALUES or value_norm_check == "":
            state = FieldState.BLANK
        else:
            state = FieldState.VALUE

        existing = fields.get(field)
        if existing is not None:
            new_raw = raw_value if state == FieldState.VALUE else None
            if existing.raw_value == new_raw:
                continue  # identical duplicate label, nothing new to record
            # Two different labels disagree on the same field: don't guess
            # which one is right, flag it for review instead.
            fields[field] = ExtractedField(
                field=field,
                source_label=f"{existing.source_label} / {label.strip()}",
                raw_value=None,
                state=FieldState.BLANK,
                method="rule",
                confidence=1.0,
                evidence_quote=f"{existing.evidence_quote} | {line.strip()}",
            )
            continue

        fields[field] = ExtractedField(
            field=field,
            source_label=label.strip(),
            raw_value=raw_value if state == FieldState.VALUE else None,
            state=state,
            method="rule",
            confidence=1.0,
            evidence_quote=line.strip(),
        )
    return DocumentExtraction(
        role=role,
        filename=filename,
        doc_kind=doc_kind,
        readable=True,
        fields=fields,
        raw_text=text,
    )
