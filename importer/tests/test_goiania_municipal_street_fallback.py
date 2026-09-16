from otimizer_importer.goiania import GoianiaLocationProvider
from otimizer_importer.location import LocationEvidence


def street_evidence(*, neighborhood="Setor Bueno"):
    return LocationEvidence(
        address="Avenida New York",
        normalized_address="avenida new york",
        number="250",
        neighborhood=neighborhood,
        city="Goiânia",
    )


def municipal_street_feature():
    return {
        "attributes": {
            "id": "STREET-1",
            "tp_log": "Avenida",
            "nm_log": "Avenida New York",
            "nm": "Avenida New York",
            "nm_bai": "Setor Bueno",
        },
        "geometry": {
            "paths": [[[-49.2800, -16.7000], [-49.2700, -16.7000], [-49.2600, -16.7000]]]
        },
    }


def test_address_only_stop_uses_real_municipal_street_point(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    feature = municipal_street_feature()
    calls = []

    def query_layer(layer_id, where, out_fields):
        calls.append((layer_id, where))
        if layer_id == 10 and "nm_bai" in where:
            return [feature]
        return []

    monkeypatch.setattr(provider, "_query_layer_where", query_layer)

    resolved = provider.resolve(street_evidence())

    assert resolved is not None
    assert resolved.source == "goiania-municipal-street"
    assert resolved.longitude == -49.275
    assert resolved.latitude == -16.7
    assert resolved.access_longitude == -49.275
    assert resolved.access_latitude == -16.7
    assert calls and calls[0][0] == 10
    assert "Avenida New York" in calls[0][1]
    assert "Setor Bueno" in calls[0][1]


def test_address_only_stop_can_fall_back_without_neighborhood(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    feature = municipal_street_feature()

    def query_layer(layer_id, where, out_fields):
        if layer_id == 10 and "nm_bai" not in where:
            return [feature]
        return []

    monkeypatch.setattr(provider, "_query_layer_where", query_layer)

    resolved = provider.resolve(street_evidence(neighborhood="Bairro inexistente"))

    assert resolved is not None
    assert resolved.source == "goiania-municipal-street"
    assert resolved.longitude == -49.275
    assert resolved.latitude == -16.7
