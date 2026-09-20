import re


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().casefold())


def evidence_supports_value(source_text: str, evidence: str | None, value: str | None) -> bool:
    """A Gemini-extracted field is only trusted if its evidence quote actually
    appears in the source, and the claimed value actually appears in that quote."""
    if not evidence or not value or not source_text:
        return False
    source_norm = _norm(source_text)
    evidence_norm = _norm(evidence)
    value_norm = _norm(value)
    return evidence_norm in source_norm and value_norm in evidence_norm
