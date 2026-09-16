import math

from otimizer_importer.goiania import (
    GoianiaLocationProvider,
    _best_matching_cadastral_record,
)
from otimizer_importer.location import LocationEvidence


def parcel_evidence(*, latitude=-16.68, longitude=-49.25, number="123"):
    return LocationEvidence(
        latitude=latitude,
        longitude=longitude,
        address="Rua Exemplo, 123, Qd 10 Lt 5",
        normalized_address="rua exemplo 123 qd 10 lt 5",
        number=number,
        quadra="10",
        lote="5",
        zipcode="74000-000",
        neighborhood="Centro",
        city="Goiânia",
    )


def cadastral_feature(*, number="123", street="Rua Exemplo", neighborhood="Centro", quadra="10", lote="5", geometry=None):
    if geometry is None:
        geometry = {
            "rings": [[[-49.251, -16.681], [-49.250, -16.681], [-49.250, -16.680], [-49.251, -16.680], [-49.251, -16.681]]]
        }
    return {
        "attributes": {
            "id": "CAD-123",
            "id_qdr": "QDR-10",
            "nrinscr": "123456789",
            "nrimovel": number,
            "nrquadra": quadra,
            "nrlote": lote,
            "nmbairro": neighborhood,
            "nmlogradou": street,
            "cdlogradou": 777,
            "ci": "CI-123",
        },
        "geometry": geometry,
    }


def segment_feature(segment_id, *, logradouro=777, street="Rua Exemplo", path=None):
    return {
        "attributes": {
            "id": segment_id,
            "id_log": str(logradouro),
            "nm_log": street,
            "nm": street,
        },
        "geometry": {"paths": [path or [[-49.2500, -16.6800], [-49.2490, -16.6800]]]},
    }


def test_best_cadastral_record_cross_checks_number_street_and_parcel():
    evidence = parcel_evidence(number="123")
    wrong_number = cadastral_feature(number="125")
    exact = cadastral_feature(number="123")

    resolved = _best_matching_cadastral_record(evidence, [wrong_number, exact])

    assert resolved == exact


def test_provider_prefers_cadastral_cross_check_before_gps_only_sources(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    feature = cadastral_feature(number="123")
    calls = {"cadastral": 0, "official": 0, "lots": 0}

    def query_cadastral(current_evidence):
        calls["cadastral"] += 1
        return [feature]

    monkeypatch.setattr(provider, "_query_cadastral_by_parcel", query_cadastral)
    monkeypatch.setattr(provider, "_query_lot_segment_ids", lambda block_id, lot: [])
    monkeypatch.setattr(provider, "_query_street_segments_by_link", lambda **kwargs: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])
    monkeypatch.setattr(provider, "_query_official_numbers", lambda current_evidence: calls.__setitem__("official", calls["official"] + 1) or [])
    monkeypatch.setattr(provider, "_query_lots", lambda current_evidence: calls.__setitem__("lots", calls["lots"] + 1) or [])

    resolved = provider.resolve(parcel_evidence())

    assert resolved is not None
    assert resolved.source == "goiania-cadastral-crosscheck"
    assert resolved.cadastral_id == "CAD-123"
    assert math.isclose(resolved.property_latitude, -16.6805, abs_tol=1e-9)
    assert math.isclose(resolved.property_longitude, -49.2505, abs_tol=1e-9)
    assert resolved.confidence == 0.93
    assert calls == {"cadastral": 1, "official": 0, "lots": 0}


def test_provider_uses_cadastral_x_y_when_geometry_is_missing(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    feature = cadastral_feature(number="123", geometry={})
    feature["attributes"]["x_coord"] = -49.2505
    feature["attributes"]["y_coord"] = -16.6805

    monkeypatch.setattr(provider, "_query_cadastral_by_parcel", lambda evidence: [feature])
    monkeypatch.setattr(provider, "_query_lot_segment_ids", lambda block_id, lot: [])
    monkeypatch.setattr(provider, "_query_street_segments_by_link", lambda **kwargs: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])

    resolved = provider.resolve(parcel_evidence())

    assert resolved is not None
    assert resolved.longitude == -49.2505
    assert resolved.latitude == -16.6805


def test_provider_does_not_accept_cadastral_candidate_with_wrong_lot(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    weak = cadastral_feature(number="999", street="Outra Rua", neighborhood="Outro Bairro", lote="6")

    monkeypatch.setattr(provider, "_query_cadastral_by_parcel", lambda evidence: [weak])
    monkeypatch.setattr(provider, "_query_lot_by_parcel", lambda evidence: [])
    monkeypatch.setattr(provider, "_query_official_numbers", lambda evidence: [])
    monkeypatch.setattr(provider, "_query_lots", lambda evidence: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])

    resolved = provider.resolve(parcel_evidence())

    assert resolved is None


def test_nearest_access_prefers_explicit_parcel_segment_over_closer_neighbor(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    property_point = (-49.2505, -16.6805)
    linked = segment_feature("SEG-LINKED", path=[[-49.2505, -16.6810], [-49.2505, -16.6800]])
    closer_wrong = segment_feature("SEG-WRONG", path=[[-49.2501, -16.6805], [-49.2491, -16.6805]], street="Outra Rua")

    monkeypatch.setattr(provider, "_query_street_segments_by_link", lambda **kwargs: [linked, closer_wrong])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])

    access = provider._nearest_street_access(
        property_point,
        preferred_segment_ids=["SEG-LINKED"],
        preferred_logradouro=777,
        preferred_street_name="Rua Exemplo",
    )

    assert access is not None
    assert math.isclose(access[0], -49.2505, abs_tol=1e-9)
    assert math.isclose(access[1], -16.6805, abs_tol=1e-9)


def test_nearest_access_falls_back_to_spatial_segments_when_link_is_unavailable(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    property_point = (-49.2505, -16.6805)
    spatial = segment_feature("SEG-SPATIAL", path=[[-49.2505, -16.6810], [-49.2505, -16.6800]])

    monkeypatch.setattr(provider, "_query_street_segments_by_link", lambda **kwargs: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [spatial])

    access = provider._nearest_street_access(property_point, preferred_segment_ids=["SEG-MISSING"])

    assert access is not None
    assert math.isclose(access[0], -49.2505, abs_tol=1e-9)
    assert math.isclose(access[1], -16.6805, abs_tol=1e-9)
