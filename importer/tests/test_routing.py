import json

import pytest

from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.routing import (
    RoutingError,
    TravelMetric,
    build_osrm_table_url,
    build_route_matrix,
    parse_osrm_table,
)


def stop(index: int, latitude: float, longitude: float) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}", latitude=latitude, longitude=longitude,
        deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, latitude, longitude)],
    )


def test_osrm_table_url_uses_longitude_latitude_and_driving_profile():
    url = build_osrm_table_url([stop(1, -16.7, -49.2), stop(2, -16.71, -49.21)])
    assert "/table/v1/driving/-49.2,-16.7;-49.21,-16.71" in url
    assert "annotations=distance,duration" in url


def test_parse_osrm_table_preserves_unreachable_pairs():
    payload = json.dumps({"code": "Ok", "distances": [[0, 1200], [None, 0]], "durations": [[0, 180], [None, 0]]})
    matrix = parse_osrm_table(payload, expected_size=2)
    assert matrix[0][1] == TravelMetric(1200.0, 180.0)
    assert matrix[1][0] is None


def test_parse_osrm_table_rejects_provider_error():
    with pytest.raises(RoutingError, match="NoRoute"):
        parse_osrm_table('{"code":"NoRoute"}', expected_size=2)


def test_parse_osrm_table_rejects_wrong_matrix_size():
    payload = json.dumps({"code": "Ok", "distances": [[0]], "durations": [[0]]})
    with pytest.raises(RoutingError, match="matrix size"):
        parse_osrm_table(payload, expected_size=2)


def test_build_route_matrix_uses_injected_provider():
    class FakeProvider:
        def __init__(self):
            self.locations = None

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
