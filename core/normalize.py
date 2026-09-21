"""Deterministic per-field normalizers.

data/README.md states no numeric tolerance for the comparison, so gross
weight and container count are compared as exact values after parsing units
and separators. See README Decisions log.
"""
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_PORT_CODE_RE = re.compile(r"\(([A-Z]{2}[A-Z0-9]{3})\)\s*$")
_PORT_CODE_PREFIX_RE = re.compile(r"^([A-Z]{2}[A-Z0-9]{3})\s*[-:]\s*", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_name(value: str) -> str:
    # NFKC folds e.g. "E" + combining-acute into the precomposed "É" (and
    # compatibility variants like full-width letters) so two documents
    # encoding the same name differently don't look like a real defect.
    value = unicodedata.normalize("NFKC", value.strip()).casefold()
    value = _PUNCT_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value)
    return value.strip()


def normalize_port(value: str) -> str:
    """The port name only, for display; see ports_match() for the actual
    comparison, which also checks the UNLOCODE when both sides have one."""
    name, _code = _parse_port(value)
    return name


def _parse_port(value: str) -> tuple[str, str | None]:
    """(normalized name, UNLOCODE or None). Handles a trailing "(CODE)" and
    a leading "CODE - NAME" form."""
    value = value.strip()
    m = _PORT_CODE_RE.search(value)
    if m:
        return normalize_name(value[: m.start()]), m.group(1).upper()
    m = _PORT_CODE_PREFIX_RE.match(value)
    if m:
        return normalize_name(value[m.end():]), m.group(1).upper()
    return normalize_name(value), None


def ports_match(si_raw: str, bl_raw: str) -> bool:
    """Port names must always match. A UNLOCODE is supporting evidence, not
    a required field: a code-only change (name unchanged) is a real defect
    — e.g. "SHANGHAI (CNSHA)" vs "SHANGHAI (CNSGH)" — but a code present on
    only one side is not itself a mismatch."""
    si_name, si_code = _parse_port(si_raw)
    bl_name, bl_code = _parse_port(bl_raw)
    if si_name != bl_name:
        return False
    if si_code and bl_code and si_code != bl_code:
        return False
    return True


_CONTAINER_SEGMENT_RE = re.compile(r"\s*[+,]\s*")
_CONTAINER_X_RE = re.compile(r"\s*x\s*", re.IGNORECASE)


def normalize_container_count(value: str) -> int | None:
    """Parse and sum "N x TYPE" / "TYPE x N" groups, e.g. "1 x 40'HC + 2 x 20'GP".

    A bare "N" with no "x" and no other digits is also accepted. Any segment
    where both sides of "x" are ambiguous (both purely numeric, or neither is)
    makes the whole value unparseable, since we cannot tell count from type.
    """
    segments = [s for s in _CONTAINER_SEGMENT_RE.split(value.strip()) if s]
    if not segments:
        return None

    total = 0
    matched_any = False
    for segment in segments:
        parts = _CONTAINER_X_RE.split(segment.strip())
        if len(parts) != 2:
            continue
        a, b = parts[0].strip(), parts[1].strip()
        a_is_count, b_is_count = a.isdigit(), b.isdigit()
        if a_is_count and not b_is_count:
            total += int(a)
            matched_any = True
        elif b_is_count and not a_is_count:
            total += int(b)
            matched_any = True
        else:
            return None

    if matched_any:
        return total

    numbers = re.findall(r"\d+", value)
    if len(numbers) == 1:
        return int(numbers[0])
    return None


_WEIGHT_NUMBER_RE = re.compile(r"\d[\d.,]*\d|\d")
_WEIGHT_UNIT_RE = re.compile(r"[A-Za-z/]+")
_WEIGHT_QUANTUM = Decimal("0.00001")

_WEIGHT_UNIT_FACTORS_KG = {
    "KG": Decimal("1"),
    "KGS": Decimal("1"),
    "MT": Decimal("1000"),
    "M/T": Decimal("1000"),
    "TON": Decimal("1000"),
    "TONS": Decimal("1000"),
    "TONNE": Decimal("1000"),
    "TONNES": Decimal("1000"),
    "LB": Decimal("0.45359237"),
    "LBS": Decimal("0.45359237"),
}


def _parse_decimal_number(token: str) -> Decimal | None:
    """Parse a number that may use either English (1,234.50) or European
    (1.234,50) decimal/thousands separators. Ambiguous single-separator
    strings are only accepted when the trailing group length rules out the
    other convention.
    """
    has_dot, has_comma = "." in token, "," in token
    if has_dot and has_comma:
        if token.rfind(",") > token.rfind("."):
            cleaned = token.replace(".", "").replace(",", ".")
        else:
            cleaned = token.replace(",", "")
    elif has_comma:
        groups = token.split(",")
        trailing = groups[-1]
        if len(groups) > 2:
            if all(len(g) == 3 for g in groups[1:]):
                cleaned = token.replace(",", "")
            else:
                return None
        elif len(trailing) == 3:
            cleaned = token.replace(",", "")
        elif len(trailing) in (1, 2):
            cleaned = token.replace(",", ".")
        else:
            return None
    else:
        cleaned = token  # lone '.' (or no separator) is always the decimal point
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_gross_weight_kg(value: str) -> Decimal | None:
    """Parse a weight string into kilograms as an exact Decimal.

    Requires exactly one number and a recognised unit (KG/KGS/MT/M/T/TON(S)/
    TONNE(S)/LB(S)); anything ambiguous returns None rather than guessing.
    """
    numbers = _WEIGHT_NUMBER_RE.findall(value)
    if len(numbers) != 1:
        return None
    number = _parse_decimal_number(numbers[0])
    if number is None:
        return None

    start = value.index(numbers[0]) + len(numbers[0])
    unit_match = _WEIGHT_UNIT_RE.search(value, start)
    unit = unit_match.group(0).upper() if unit_match else None
    factor = _WEIGHT_UNIT_FACTORS_KG.get(unit)
    if factor is None:
        return None

    return (number * factor).quantize(_WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)


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
