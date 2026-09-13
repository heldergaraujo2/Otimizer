from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.routing import TravelMetric, build_route_matrix
from otimizer_importer.types import RouteEndpoint


def stop(index: int, latitude: float, longitude: float) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=latitude,
        longitude=longitude,
        deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, latitude, longitude)],
    )


def test_build_route_matrix_deduplicates_identical_coordinates():
    first = stop(1, -16.7, -49.2)
    duplicate = stop(2, -16.7, -49.2)
    other = stop(3, -16.71, -49.21)

    class FakeProvider:
        def __init__(self):
            self.calls = []

        def table(self, locations):
            self.calls.append(list(locations))
            size = len(locations)
            return tuple(
                tuple(TravelMetric(abs(i - j) * 100, abs(i - j) * 10) for j in range(size))
                for i in range(size)
            )

    provider = FakeProvider()
    matrix = build_route_matrix([first, duplicate, other], provider=provider)

    assert len(provider.calls) == 1
    assert provider.calls[0] == [first, other]
    assert len(matrix) == 3
    assert all(len(row) == 3 for row in matrix)
    assert matrix[0][1] == TravelMetric(0.0, 0.0)
    assert matrix[1][0] == TravelMetric(0.0, 0.0)
    assert matrix[0][2] == TravelMetric(100.0, 10.0)
    assert matrix[1][2] == TravelMetric(100.0, 10.0)


def test_build_route_matrix_deduplicates_endpoint_with_stop():
    shared = stop(1, -16.7, -49.2)
    origin = RouteEndpoint(-16.7, -49.2, "depot")

    class FakeProvider:
        def __init__(self):
            self.locations = None

        def table(self, locations):
            self.locations = list(locations)
            size = len(locations)
            return tuple(
                tuple(TravelMetric(50 if i != j else 0, 5 if i != j else 0) for j in range(size))
                for i in range(size)
            )

    provider = FakeProvider()
    matrix = build_route_matrix([shared], origin=origin, provider=provider)

    assert provider.locations == [origin]
    assert matrix == (
        (TravelMetric(0.0, 0.0), TravelMetric(0.0, 0.0)),
        (TravelMetric(0.0, 0.0), TravelMetric(0.0, 0.0)),
    )
