import pytest

from otimizer_importer.address_parser import parse_address


@pytest.mark.parametrize(
    ("address", "number", "quadra", "lote"),
    [
        ("Rua das Flores, 123", "123", None, None),
        ("Rua PA 9, 49, Qd 06 lt 21 casa 01", "49", "06", "21"),
        ("Avenida Central, Q 195, Qd 195 LT 25", None, "195", "25"),
        ("Rua Americano do Brasil, 04, Qd 9 lote 31", "04", "9", "31"),
        ("Rua engenheiro correa lima, 03, Q x4 LT 20", "03", "x4", "20"),
        ("Avenida Anapolis, S/N, Qd 185 A 1", None, "185", None),
        ("Rua sem numero conhecido", None, None, None),
    ],
)
def test_parse_address_extracts_available_location_evidence(address, number, quadra, lote):
    parsed = parse_address(address)
    assert parsed.original == address
    assert parsed.number == number
    assert parsed.quadra == quadra
    assert parsed.lote == lote
    assert parsed.normalized


def test_parse_address_does_not_confuse_street_number_with_house_number_when_house_number_follows_comma():
    parsed = parse_address("Rua PA 9, 49, Qd 06 Lt 21")
    assert parsed.number == "49"


def test_parse_address_accepts_missing_input():
    assert parse_address(None).normalized is None
    assert parse_address("   ").original is None
