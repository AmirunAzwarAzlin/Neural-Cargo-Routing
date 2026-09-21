import re

from core.extract_rules import FIELD_ALIASES, LINE_RE, _normalize_label

_LABEL_PREFIX_RE = re.compile(r"^[^:：]{1,60}[:：]\s*")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().casefold())


def _strip_label_prefix(evidence_norm: str) -> str:
    return _LABEL_PREFIX_RE.sub("", evidence_norm, count=1)


def _evidence_label_field(evidence: str) -> str | None:
    """Which canonical field the evidence's own leading label (if any)
    belongs to, per the same alias table core/extract_rules.py uses."""
    m = LINE_RE.match(evidence.strip())
    if not m:
        return None
    norm_label = _normalize_label(m.group(1))
    for field, aliases in FIELD_ALIASES.items():
        if norm_label in aliases:
            return field
    return None


def evidence_supports_value(
    source_text: str, evidence: str | None, value: str | None, field: str | None = None
) -> bool:
    """A Gemini-extracted field is only trusted if:
    - its evidence quote actually appears in the source,
    - the evidence's own label (if any) doesn't belong to a *different*
      canonical field (rejects e.g. the consignee's line being passed off
      as notify_party evidence), and
    - the value equals the evidence with that label stripped — not just a
      substring of it (rejects a truncated value like "APRIL" evidenced by
      "Shipper: APRIL FINE PAPER TRADING ... FZE").
    """
    if not evidence or not value or not source_text:
        return False
    source_norm = _norm(source_text)
    evidence_norm = _norm(evidence)
    value_norm = _norm(value)
    if evidence_norm not in source_norm:
        return False
    if field is not None:
        evidence_field = _evidence_label_field(evidence)
        if evidence_field is not None and evidence_field != field:
            return False
    return value_norm in (evidence_norm, _strip_label_prefix(evidence_norm))
