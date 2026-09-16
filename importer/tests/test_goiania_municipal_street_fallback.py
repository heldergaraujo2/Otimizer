from otimizer_importer.goiania import GoianiaLocationProvider
from otimizer_importer.location import LocationEvidence


def street_evidence(*, neighborhood="Setor Bueno"):
    return LocationEvidence(
        latitude=None,
        longitude=None,
        address="Avenida New York",
        normalized_address="avenida new york",
        number="250",
        quadra=None,
        lote=None,
        zipcode=None,
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


def assert_point_is_on_test_street(resolved):
    assert resolved.latitude == -16.7
    assert -49.28 <= resolved.longitude <= -49.26
    assert resolved.access_latitude == resolved.latitude
    assert resolved.access_longitude == resolved.longitude


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
    assert_point_is_on_test_street(resolved)
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
    assert_point_is_on_test_street(resolved)


def test_address_only_stop_prefers_matching_street_when_service_returns_multiple_features(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    wrong = municipal_street_feature()
    wrong["attributes"]["id"] = "STREET-WRONG"
    wrong["attributes"]["nm_log"] = "Rua Outra"
    wrong["attributes"]["nm"] = "Rua Outra"
    exact = municipal_street_feature()

    monkeypatch.setattr(
        provider,
        "_query_layer_where",
        lambda layer_id, where, out_fields: [wrong, exact] if layer_id == 10 else [],
    )

    resolved = provider.resolve(street_evidence())

    assert resolved is not None
    assert resolved.source == "goiania-municipal-street"
    assert_point_is_on_test_street(resolved)


def test_municipal_service_failure_degrades_to_unresolved_instead_of_fabricating_location(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")

    def failing_query(*args, **kwargs):
        raise OSError("municipal service unavailable")

    monkeypatch.setattr(provider, "_query_layer_where", failing_query)

    resolved = provider.resolve(street_evidence())

    assert resolved is None
