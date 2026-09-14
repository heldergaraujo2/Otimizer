import json
from urllib.parse import parse_qs, urlsplit

import pytest

from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer import routing
from otimizer_importer.routing import RoutingError, TravelMetric, build_osrm_table_url, build_route_matrix, parse_osrm_table


def stop(index: int, latitude: float, longitude: float) -> PhysicalStop:
    return PhysicalStop(id=f"stop-{index}", latitude=latitude, longitude=longitude, deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, latitude, longitude)])


def test_osrm_table_url_uses_longitude_latitude_and_driving_profile():
    url = build_osrm_table_url([stop(1, -16.7, -49.2), stop(2, -16.71, -49.21)])
    assert "/table/v1/driving/-49.2,-16.7;-49.21,-16.71" in url
    assert "annotations=distance,duration" in url


def test_osrm_table_url_supports_source_and_destination_indices():
    url = build_osrm_table_url([stop(1, -16.7, -49.2), stop(2, -16.71, -49.21), stop(3, -16.72, -49.22)], sources=[0, 1], destinations=[2])
    assert "sources=0;1" in url
    assert "destinations=2" in url


def test_parse_osrm_table_preserves_unreachable_pairs():
    payload = json.dumps({"code": "Ok", "distances": [[0, 1200], [None, 0]], "durations": [[0, 180], [None, 0]]})
    matrix = parse_osrm_table(payload, expected_size=2)
    assert matrix[0][1] == TravelMetric(1200.0, 180.0)
    assert matrix[1][0] is None


def test_parse_osrm_table_accepts_rectangular_matrix():
    payload = json.dumps({"code": "Ok", "distances": [[10, 20, None], [30, 40, 50]], "durations": [[1, 2, None], [3, 4, 5]]})
    matrix = parse_osrm_table(payload, expected_size=2, expected_columns=3)
    assert matrix == ((TravelMetric(10.0, 1.0), TravelMetric(20.0, 2.0), None), (TravelMetric(30.0, 3.0), TravelMetric(40.0, 4.0), TravelMetric(50.0, 5.0)))


def test_parse_osrm_table_rejects_provider_error():
    with pytest.raises(RoutingError, match="NoRoute"):
        parse_osrm_table('{"code":"NoRoute"}', expected_size=2)


def test_parse_osrm_table_rejects_wrong_matrix_size():
    payload = json.dumps({"code": "Ok", "distances": [[0]], "durations": [[0]]})
    with pytest.raises(RoutingError, match="matrix size"):
        parse_osrm_table(payload, expected_size=2)


def test_parse_osrm_table_rejects_negative_metric():
    payload = json.dumps({"code": "Ok", "distances": [[0, -1], [0, 0]], "durations": [[0, 1], [0, 0]]})
    with pytest.raises(RoutingError, match="invalid metric"):
        parse_osrm_table(payload, expected_size=2)


def test_parse_osrm_table_rejects_non_finite_metric():
    payload = '{"code":"Ok","distances":[[0,NaN],[0,0]],"durations":[[0,1],[0,0]]}'
    with pytest.raises(RoutingError, match="invalid metric"):
        parse_osrm_table(payload, expected_size=2)


def test_fetch_osrm_table_batches_large_matrix(monkeypatch):
    locations = [stop(index, -16.0 - index, -49.0 - index) for index in range(5)]
    requests = []

    class FakeResponse:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return self.payload

    def fake_urlopen(request, timeout):
        parsed = urlsplit(request.full_url)
        query = parse_qs(parsed.query)
        coordinates = parsed.path.split("/driving/", 1)[1].split("?")[0].split(";")
        source_indices = [int(value) for value in query["sources"][0].split(";")] if "sources" in query else list(range(len(coordinates)))
        destination_indices = [int(value) for value in query["destinations"][0].split(";")] if "destinations" in query else list(range(len(coordinates)))
        requests.append((source_indices, destination_indices, coordinates))
        distances, durations = [], []
        for source_index in source_indices:
            source_id = float(coordinates[source_index].split(",")[0])
            distance_row, duration_row = [], []
            for destination_index in destination_indices:
                destination_id = float(coordinates[destination_index].split(",")[0])
                distance_row.append(abs(source_id - destination_id) * 1000)
                duration_row.append(abs(source_id - destination_id) * 10)
            distances.append(distance_row); durations.append(duration_row)
        return FakeResponse(json.dumps({"code": "Ok", "distances": distances, "durations": durations}).encode())

    monkeypatch.setattr(routing, "urlopen", fake_urlopen)
    matrix = routing.fetch_osrm_table(locations, max_locations=3)
    assert len(requests) == 11
    assert all(len(request[2]) <= 3 for request in requests)
    assert sum(1 for request in requests if request[0] == [0, 1] and request[1] == [0, 1]) == 2
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
        def __init__(self): self.locations = None
        def table(self, locations):
            self.locations = list(locations)
            size = len(locations)
            return tuple(tuple(TravelMetric(100.0 if i != j else 0.0, 10.0 if i != j else 0.0) for j in range(size)) for i in range(size))

    provider = FakeProvider()
    origin = stop(9, -16.6, -49.1)
    destination = stop(10, -16.8, -49.3)
    matrix = build_route_matrix([stop(1, -16.7, -49.2)], origin=origin, destination=destination, provider=provider)
    assert len(matrix) == 3
    assert provider.locations == [origin, stop(1, -16.7, -49.2), destination]
