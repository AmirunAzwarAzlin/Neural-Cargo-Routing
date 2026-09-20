"""Deterministic per-field normalizers.

data/README.md states no numeric tolerance for the comparison, so gross
weight and container count are compared as exact values after parsing units
and separators. See README Decisions log.
"""
import re

_PORT_CODE_RE = re.compile(r"\(([A-Z]{2}[A-Z0-9]{3})\)\s*$")
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_name(value: str) -> str:
    value = value.strip().casefold()
    value = _PUNCT_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value)
    return value.strip()


def normalize_port(value: str) -> str:
    """Compare by port name only; a bracketed UNLOCODE is supporting evidence."""
    value = _PORT_CODE_RE.sub("", value).strip()
    return normalize_name(value)


def normalize_container_count(value: str) -> int | None:
    """Parse the leading integer from forms like "6 x 40'HC" or "10 x 20'FCL"."""
    m = re.search(r"(\d+)", value)
    if not m:
        return None
    return int(m.group(1))


def normalize_gross_weight_kg(value: str) -> float | None:
    """Parse a weight string into kilograms. Handles KG/KGS/MT and thousands separators."""
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(KGS?|MT|KG)?", value, re.IGNORECASE)
    if not m:
        return None
    number_str = m.group(1).replace(",", "")
    try:
        number = float(number_str)
    except ValueError:
        return None
    unit = (m.group(2) or "KG").upper()
    if unit == "MT":
        number *= 1000
    return number


NORMALIZERS = {
    "shipper": normalize_name,
    "consignee": normalize_name,
    "notify_party": normalize_name,
    "port_of_loading": normalize_port,
    "port_of_discharge": normalize_port,
    "container_count": normalize_container_count,
    "gross_weight_kg": normalize_gross_weight_kg,
}


def normalize_field(field: str, raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    fn = NORMALIZERS.get(field)
    if fn is None:
        return raw_value
    result = fn(raw_value)
    return str(result) if result is not None else None
