from otimizer_importer.goiania import (
    GoianiaLocationProvider,
    _nearest_point_on_segment,
    _point_from_geometry,
    _representative_point,
)
from otimizer_importer.location import LocationEvidence


def evidence(city="Goiânia", number="123"):
    return LocationEvidence(
        latitude=-16.6800,
        longitude=-49.2500,
        address="Rua Exemplo, 123, Qd 10 Lt 5",
        normalized_address="rua exemplo 123 qd 10 lt 5",
        number=number,
        quadra="10",
        lote="5",
        zipcode="74000-000",
        neighborhood="Centro",
        city=city,
    )


def test_goiania_provider_ignores_other_cities():
    provider = GoianiaLocationProvider(base_url="https://example.invalid")
    assert provider.resolve(evidence("Anápolis")) is None


def test_representative_point_from_polygon():
    point = _representative_point({"rings": [[[1, 2], [3, 2], [3, 4], [1, 4], [1, 2]]]})
    assert point == (2.0, 3.0)


def test_representative_point_handles_missing_geometry():
    assert _representative_point({}) is None


def test_point_from_arcgis_point_geometry():
    assert _point_from_geometry({"x": -49.25, "y": -16.68}) == (-49.25, -16.68)
    assert _point_from_geometry({}) is None


def test_nearest_point_on_street_segment():
    assert _nearest_point_on_segment((5.0, 2.0), [0.0, 0.0], [10.0, 0.0]) == (5.0, 0.0)
    assert _nearest_point_on_segment((20.0, 2.0), [0.0, 0.0], [10.0, 0.0]) == (10.0, 0.0)


def test_provider_prefers_exact_official_property_number(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    monkeypatch.setattr(
        provider,
        "_query_official_numbers",
        lambda evidence: [
            {
                "attributes": {"id": "NPO-123", "nm_npo": "123"},
                "geometry": {"x": -49.251, "y": -16.681},
            },
            {
                "attributes": {"id": "NPO-999", "nm_npo": "999"},
                "geometry": {"x": -49.2501, "y": -16.6801},
            },
        ],
    )
    monkeypatch.setattr(provider, "_query_lots", lambda evidence: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])

    resolved = provider.resolve(evidence())
    assert resolved is not None
    assert resolved.source == "goiania-official-property-number"
    assert resolved.cadastral_id == "NPO-123"
    assert resolved.confidence == 0.92
    assert resolved.latitude == -16.681
    assert resolved.longitude == -49.251


def test_provider_uses_street_segment_as_vehicle_access_candidate(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    monkeypatch.setattr(
        provider,
        "_query_official_numbers",
        lambda evidence: [
            {
                "attributes": {"id": "NPO-123", "nm_npo": "123"},
                "geometry": {"x": 5.0, "y": 2.0},
            }
        ],
    )
    calls = []

    def query_street_segments(latitude, longitude):
        calls.append((latitude, longitude))
        return [{"geometry": {"paths": [[[0.0, 0.0], [10.0, 0.0]]]}}]

    monkeypatch.setattr(provider, "_query_street_segments", query_street_segments)
    monkeypatch.setattr(provider, "_query_lots", lambda evidence: [])

    resolved = provider.resolve(evidence())
    assert resolved is not None
    assert resolved.source == "goiania-official-property-number-road-access"
    assert resolved.property_longitude == 5.0
    assert resolved.property_latitude == 2.0
    assert resolved.access_longitude == 5.0
    assert resolved.access_latitude == 0.0
    assert resolved.longitude == 5.0
    assert resolved.latitude == 0.0
    assert resolved.confidence == 0.96
    assert calls == [(2.0, 5.0)]


def test_provider_falls_back_to_cadastral_lot_without_number_match(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    monkeypatch.setattr(provider, "_query_official_numbers", lambda evidence: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])
    monkeypatch.setattr(
        provider,
        "_query_lots",
        lambda evidence: [
            {
                "attributes": {"id": "LOT-123"},
                "geometry": {
                    "rings": [[[1, 2], [3, 2], [3, 4], [1, 4], [1, 2]]]
                },
            }
        ],
    )

    resolved = provider.resolve(evidence())
    assert resolved is not None
    assert resolved.source == "goiania-cadastral-lot"
    assert resolved.cadastral_id == "LOT-123"
    assert resolved.confidence == 0.80
    assert resolved.property_latitude == resolved.latitude
    assert resolved.property_longitude == resolved.longitude


def test_provider_caches_resolution_for_identical_evidence(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    calls = {"official": 0, "street": 0}

    def query_official_numbers(evidence):
        calls["official"] += 1
        return [
            {
                "attributes": {"id": "NPO-123", "nm_npo": "123"},
                "geometry": {"x": -49.251, "y": -16.681},
            }
        ]

    def query_street_segments(latitude, longitude):
        calls["street"] += 1
        return []

    monkeypatch.setattr(provider, "_query_official_numbers", query_official_numbers)
    monkeypatch.setattr(provider, "_query_street_segments", query_street_segments)

    first = provider.resolve(evidence())
    second = provider.resolve(evidence())

    assert first == second
    assert calls == {"official": 1, "street": 1}


def test_provider_cache_key_keeps_distinct_address_evidence_separate(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    calls = []

    def query_official_numbers(current_evidence):
        calls.append(current_evidence.number)
        return []

    monkeypatch.setattr(provider, "_query_official_numbers", query_official_numbers)
    monkeypatch.setattr(provider, "_query_lots", lambda current_evidence: [])

    assert provider.resolve(evidence(number="123")) is None
    assert provider.resolve(evidence(number="125")) is None
    assert provider.resolve(evidence(number="123")) is None
    assert calls == ["123", "125"]
