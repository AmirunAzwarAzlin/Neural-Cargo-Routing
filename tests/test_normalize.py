import pytest

from core.normalize import (
    normalize_container_count,
    normalize_gross_weight_kg,
    normalize_name,
    normalize_port,
    ports_match,
)


def test_normalize_name_case_and_punctuation():
    assert normalize_name("Moorim SP Co., Ltd") == normalize_name("MOORIM SP CO. LTD")


def test_normalize_name_nfkc_normalizes_combining_characters():
    # "E" + U+0301 COMBINING ACUTE ACCENT vs U+00C9 "E WITH ACUTE" - visually
    # identical, different byte sequences, and a false mismatch if not
    # normalized. Built via chr() to avoid the source file itself silently
    # normalizing one form into the other.
    precomposed = "SOCI" + chr(0xC9) + "T" + chr(0xC9)
    decomposed = "SOCI" + "E" + chr(0x0301) + "T" + "E" + chr(0x0301)
    assert decomposed != precomposed  # sanity: genuinely different byte sequences
    assert normalize_name(precomposed) == normalize_name(decomposed)


def test_normalize_port_strips_unlocode():
    a = normalize_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)")
    b = normalize_port("PORT KLANG (WESTPORT), MALAYSIA")
    assert a == b


def test_normalize_port_different_names_do_not_match():
    a = normalize_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)")
    b = normalize_port("PORT KLANG (NORTHPORT), MALAYSIA (MYPKG)")
    assert a != b


def test_ports_match_same_name_and_code():
    assert ports_match("SHANGHAI (CNSHA)", "SHANGHAI (CNSHA)")


def test_ports_match_flags_code_only_change():
    # same name, different UNLOCODE: a real defect the old name-only
    # comparison silently hid.
    assert not ports_match("SHANGHAI (CNSHA)", "SHANGHAI (CNSGH)")


def test_ports_match_flags_name_change():
    assert not ports_match("SHANGHAI (CNSHA)", "TOKYO (CNSHA)")


def test_ports_match_tolerates_code_present_on_only_one_side():
    # a code is supporting evidence, not a required field — its absence on
    # one side alone must not itself trigger a mismatch.
    assert ports_match("SHANGHAI (CNSHA)", "SHANGHAI")


def test_ports_match_handles_code_dash_name_form():
    assert ports_match("CNSHA - SHANGHAI", "SHANGHAI (CNSHA)")


def test_normalize_container_count():
    assert normalize_container_count("6 x 40'HC") == 6
    assert normalize_container_count("10 x 20'FCL") == 10
    assert normalize_container_count("1 x 40'HC") == 1


def test_normalize_container_count_type_before_count():
    assert normalize_container_count("40'HC x 6") == 6


def test_normalize_container_count_multi_type_sums_groups():
    assert normalize_container_count("1 x 40'HC + 2 x 20'GP") == 3
    assert normalize_container_count("1 x 40'HC + 5 x 20'GP") == 6
    assert normalize_container_count("1 x 40'HC + 2 x 20'GP") != normalize_container_count(
        "1 x 40'HC + 5 x 20'GP"
    )


def test_normalize_container_count_unrecognized_multi_number_returns_none():
    assert normalize_container_count("3 and 5 containers") is None


def test_normalize_gross_weight_kg():
    assert normalize_gross_weight_kg("21,577 KG") == 21577.0
    assert normalize_gross_weight_kg("67,311 KGS") == 67311.0


def test_normalize_gross_weight_mt_converts_to_kg():
    assert normalize_gross_weight_kg("22.5 MT") == 22500.0


def test_normalize_gross_weight_lbs_converts_to_kg():
    assert float(normalize_gross_weight_kg("25,000 LBS")) == pytest.approx(11339.80925)


def test_normalize_gross_weight_m_slash_t_converts_to_kg():
    assert normalize_gross_weight_kg("12.5 M/T") == 12500


def test_normalize_gross_weight_tons_converts_to_kg():
    assert normalize_gross_weight_kg("12.5 TONS") == 12500


def test_normalize_gross_weight_european_decimal_format():
    assert normalize_gross_weight_kg("1.234,50 KG") == pytest.approx(1234.50)


def test_normalize_gross_weight_thousands_and_decimal_kg():
    assert normalize_gross_weight_kg("12,500.00 KGS") == 12500


def test_normalize_gross_weight_plain_mt():
    assert normalize_gross_weight_kg("12.5 MT") == 12500


def test_normalize_gross_weight_plain_kg():
    assert normalize_gross_weight_kg("12500 KG") == 12500


def test_normalize_gross_weight_multiple_numbers_returns_none():
    assert normalize_gross_weight_kg("6 x 20,000 KGS") is None


def test_normalize_gross_weight_unrecognized_unit_returns_none():
    assert normalize_gross_weight_kg("500 STONES") is None
