from __future__ import annotations

import json

import pytest

from otimizer_importer.models import PhysicalStop
from otimizer_importer.routing import RoutingError, TravelMetric, build_route_matrix, fetch_osrm_table, parse_osrm_table
import otimizer_importer.routing as routing


def stop(index: int, latitude: float, longitude: float) -> PhysicalStop:
    from otimizer_importer.models import Delivery

    return PhysicalStop(
        id=f"stop-{index}",
        latitude=latitude,
        longitude=longitude,
        deliveries=[
            Delivery(
                row_number=index + 1,
                source_id=f"id-{index}",
                source_sequence=None,
                source_stop=None,
                tracking_number=f"TN-{index}",
                address=None,
                neighborhood=None,
                city="Goiânia",
                zipcode=None,
                latitude=latitude,
                longitude=longitude,
            )
        ],
    )


def test_parse_osrm_table_rejects_invalid_matrix_size():
    with pytest.raises(RoutingError):
        parse_osrm_table({"code": "Ok", "distances": [[0]], "durations": [[0]]}, expected_size=2)


def test_parse_osrm_table_rejects_provider_error():
    with pytest.raises(RoutingError, match="NoRoute"):
        parse_osrm_table({"code": "NoRoute", "message": "NoRoute"}, expected_size=2)


def test_parse_osrm_table_returns_metrics():
    result = parse_osrm_table(
        {"code": "Ok", "distances": [[0, 100], [100, 0]], "durations": [[0, 10], [10, 0]]},
        expected_size=2,
    )
    assert result == (
        (TravelMetric(0.0, 0.0), TravelMetric(100.0, 10.0)),
        (TravelMetric(100.0, 10.0), TravelMetric(0.0, 0.0)),
    )


def test_fetch_osrm_table_batches_large_matrix(monkeypatch):
    locations = [stop(index, -16.0 - index, -49.0 - index) for index in range(5)]
    requests = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(request.full_url).query)
        sources = [int(value) for value in query["sources"][0].split(";")]
        destinations = [int(value) for value in query["destinations"][0].split(";")]
        coordinates = query["coordinates"][0].split(";")
        requests.append((sources, destinations, coordinates))
        distances, durations = [], []
        for source_index in sources:
            source_id = float(coordinates[source_index].split(",")[0])
            distance_row, duration_row = [], []
            for destination_index in destinations:
                destination_id = float(coordinates[destination_index].split(",")[0])
                distance_row.append(abs(source_id - destination_id) * 1000)
                duration_row.append(abs(source_id - destination_id) * 10)
            distances.append(distance_row)
            durations.append(duration_row)
        return FakeResponse(json.dumps({"code": "Ok", "distances": distances, "durations": durations}).encode())

    monkeypatch.setattr(routing, "urlopen", fake_urlopen)
    matrix = routing.fetch_osrm_table(locations, max_locations=3)

    # Five locations with a tile size of two produce a 3x3 source/destination
    # grid: 9 requests. The previous test expected 11 by incorrectly assuming
    # a one-dimensional batching strategy.
    assert len(requests) == 9
    assert all(len(request[2]) <= 3 for request in requests)
    assert sum(
        1
        for request in requests
        if request[0] == [0, 1]
        and request[1] == [0, 1]
        and request[2][0] == "-49.0,-16.0"
        and request[2][1] == "-50.0,-17.0"
    ) == 1
    assert len(matrix) == 5
    assert all(len(row) == 5 for row in matrix)
    assert all(value is not None for row in matrix for value in row)
    assert matrix[0][4] == TravelMetric(4000.0, 40.0)
    assert matrix[4][0] == TravelMetric(4000.0, 40.0)
    assert matrix[2][2] == TravelMetric(0.0, 0.0)


def test_fetch_osrm_table_reports_failed_tile_coordinates(monkeypatch):
    locations = [stop(index, -16.0 - index, -49.0 - index) for index in range(5)]

    def fail_first_tile(tile_locations, **kwargs):
        if kwargs.get("sources") is None and kwargs.get("destinations") is None and len(tile_locations) == 2 and tile_locations[0].id == "stop-0":
            raise RoutingError("Routing provider returned NoRoute")
        if kwargs.get("sources") is None and kwargs.get("destinations") is None:
            size = len(tile_locations)
            return tuple(tuple(TravelMetric(0.0, 0.0) for _ in range(size)) for _ in range(size))
        return tuple(tuple(TravelMetric(0.0, 0.0) for _ in kwargs["destinations"]) for _ in kwargs["sources"])

    monkeypatch.setattr(routing, "_fetch_osrm_request", fail_first_tile)
    with pytest.raises(RoutingError, match=r"OSRM tile failed .*sources 0:2.*destinations 0:2"):
        routing.fetch_osrm_table(locations, max_locations=3, max_concurrent_requests=1)


def test_build_route_matrix_uses_injected_provider():
    class FakeProvider:
        def __init__(self):
            self.locations = None

        def table(self, locations):
            self.locations = list(locations)
            size = len(locations)
            return tuple(
                tuple(TravelMetric(100.0 if i != j else 0.0, 10.0 if i != j else 0.0) for j in range(size))
                for i in range(size)
            )

    provider = FakeProvider()
    origin = stop(9, -16.6, -49.1)
    destination = stop(10, -16.8, -49.3)
    matrix = build_route_matrix([stop(1, -16.7, -49.2)], origin=origin, destination=destination, provider=provider)
    assert len(matrix) == 3
    assert provider.locations == [origin, stop(1, -16.7, -49.2), destination]
