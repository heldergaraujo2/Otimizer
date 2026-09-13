from otimizer_importer.goiania import GoianiaLocationProvider, _representative_point
from otimizer_importer.location import LocationEvidence


def evidence(city="Goiânia"):
    return LocationEvidence(
        latitude=-16.6800,
        longitude=-49.2500,
        address="Rua Exemplo, 123, Qd 10 Lt 5",
        normalized_address="rua exemplo 123 qd 10 lt 5",
        number="123",
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
    assert point == (2.2, 2.8)


def test_representative_point_handles_missing_geometry():
    assert _representative_point({}) is None


def test_provider_maps_cadastral_feature(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    monkeypatch.setattr(
        provider,
        "_query_layer",
        lambda layer_id, evidence, out_fields: [
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
