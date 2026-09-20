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
    norm = _normalize_label(label)
    if not norm:
        return None
    for field, aliases in FIELD_ALIASES.items():
        if norm in aliases:
            return field
    # fallback substring heuristics (kept narrow to avoid false positives)
    if "container" in norm:
        return "container_count"
    if "gross weight" in norm or "gross wt" in norm:
        return "gross_weight_kg"
    if "notify" in norm:
        return "notify_party"
    if "consignee" in norm and "notify" not in norm:
        return "consignee"
    if ("shipper" in norm or norm == "exporter") and "consignee" not in norm:
        return "shipper"
    if "discharge" in norm or norm == "pod":
        return "port_of_discharge"
    if "loading" in norm or "load port" in norm or norm == "pol":
        return "port_of_loading"
    return None


def detect_doc_kind(text: str) -> str:
    banner_match = re.search(r"\*{2,}.*NOT\s+(?:A|AN)\s+(?:SHIPPING INSTRUCTION|SI OR BL|BILL OF LADING).*\*{2,}", text, re.IGNORECASE)
    header = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not set(stripped) <= {"="}:
            header = stripped.upper()
            break
    kind = "OTHER"
    for needle, mapped in HEADER_KIND_MAP:
        if needle in header:
            kind = mapped
            break
    if banner_match and kind in ("SI", "BL"):
        # header claimed SI/BL but body explicitly disclaims it
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
        if field is None or field in fields:
            continue
        raw_value = raw_value.strip()
        value_norm_check = raw_value.strip("_ ").lower()
        if value_norm_check in BLANK_VALUES or value_norm_check == "":
            state = FieldState.BLANK
        else:
            state = FieldState.VALUE
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
