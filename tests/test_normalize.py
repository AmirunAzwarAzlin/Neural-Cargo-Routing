from core.normalize import (
    normalize_container_count,
    normalize_gross_weight_kg,
    normalize_name,
    normalize_port,
)


def test_normalize_name_case_and_punctuation():
    assert normalize_name("Moorim SP Co., Ltd") == normalize_name("MOORIM SP CO. LTD")


def test_normalize_port_strips_unlocode():
    a = normalize_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)")
    b = normalize_port("PORT KLANG (WESTPORT), MALAYSIA")
    assert a == b


def test_normalize_port_different_names_do_not_match():
    a = normalize_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)")
    b = normalize_port("PORT KLANG (NORTHPORT), MALAYSIA (MYPKG)")
    assert a != b


def test_normalize_container_count():
    assert normalize_container_count("6 x 40'HC") == 6
    assert normalize_container_count("10 x 20'FCL") == 10
    assert normalize_container_count("1 x 40'HC") == 1


def test_normalize_gross_weight_kg():
    assert normalize_gross_weight_kg("21,577 KG") == 21577.0
    assert normalize_gross_weight_kg("67,311 KGS") == 67311.0


def test_normalize_gross_weight_mt_converts_to_kg():
    assert normalize_gross_weight_kg("22.5 MT") == 22500.0
