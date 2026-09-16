from otimizer_importer.goiania import GoianiaLocationProvider, _best_matching_cadastral_record
from otimizer_importer.location import LocationEvidence


def evidence(*, number="123", address="Rua Exemplo, 123, Qd 10 Lt 5"):
    return LocationEvidence(
        latitude=None,
        longitude=None,
        address=address,
        normalized_address=address.casefold(),
        number=number,
        quadra="10",
        lote="5",
        zipcode="74000-000",
        neighborhood="Centro",
        city="Goiânia",
    )


def feature(*, number="123", street="Rua Exemplo", neighborhood="Centro", quadra="10", lote="5"):
    return {
        "attributes": {
            "id": "CAD-1",
            "id_qdr": "QDR-10",
            "nrimovel": number,
            "nrquadra": quadra,
            "nrlote": lote,
            "nmbairro": neighborhood,
            "nmlogradou": street,
        },
        "geometry": {
            "rings": [[
                [-49.251, -16.681],
                [-49.250, -16.681],
                [-49.250, -16.680],
                [-49.251, -16.680],
                [-49.251, -16.681],
            ]]
        },
    }


def test_best_matching_rejects_explicit_number_conflict():
    result = _best_matching_cadastral_record(
        evidence(),
        [feature(number="125")],
    )

    assert result is None


def test_best_matching_rejects_explicit_street_conflict():
    result = _best_matching_cadastral_record(
        evidence(),
        [feature(street="Rua Outra")],
    )

    assert result is None


def test_provider_quarantines_conflicting_cadastral_record_instead_of_using_weaker_parcel_fallback(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    wrong_number = feature(number="125")
    calls = {"lot": 0, "official": 0, "street": 0}

    monkeypatch.setattr(provider, "_query_cadastral_by_parcel", lambda current: [wrong_number])

    def lot_fallback(current):
        calls["lot"] += 1
        return [wrong_number]

    monkeypatch.setattr(provider, "_query_lot_by_parcel", lot_fallback)
    monkeypatch.setattr(provider, "_query_official_numbers", lambda current: calls.__setitem__("official", calls["official"] + 1) or [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: calls.__setitem__("street", calls["street"] + 1) or [])

    resolved = provider.resolve(evidence())

    assert resolved is None
    assert calls == {"lot": 0, "official": 0, "street": 0}


def test_provider_still_accepts_compatible_cadastral_record(monkeypatch):
    provider = GoianiaLocationProvider(base_url="https://example.test")
    exact = feature()

    monkeypatch.setattr(provider, "_query_cadastral_by_parcel", lambda current: [exact])
    monkeypatch.setattr(provider, "_query_lot_segment_ids", lambda block_id, lot: [])
    monkeypatch.setattr(provider, "_query_street_segments_by_link", lambda **kwargs: [])
    monkeypatch.setattr(provider, "_query_street_segments", lambda latitude, longitude: [])

    resolved = provider.resolve(evidence())

    assert resolved is not None
    assert resolved.source == "goiania-cadastral-crosscheck"
