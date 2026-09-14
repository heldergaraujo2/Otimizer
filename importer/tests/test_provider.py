from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.routing import (
    OSRMRoutingProvider,
    RouteEndpoint,
    RoutingProvider,
    TravelMetric,
    build_route_matrix,
)


def make_stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=-16.70 - index * 0.001,
        longitude=-49.20 - index * 0.001,
        deliveries=[
            Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, -16.70, -49.20)
        ],
    )


class FakeRoutingProvider:
    def __init__(self, matrix):
        self.matrix = matrix
        self.locations = None

    def table(self, locations):
        self.locations = locations
        return self.matrix


def test_fake_provider_can_supply_a_routing_matrix_without_network_access():
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1000, 60)),
        (TravelMetric(1000, 60), TravelMetric(0, 0)),
    )
    provider: RoutingProvider = FakeRoutingProvider(matrix)
    stops = [make_stop(0), make_stop(1)]

    result = provider.table(stops)

    assert result == matrix


def test_osrm_provider_is_configurable():
    provider = OSRMRoutingProvider(base_url="https://example.test/router", timeout_seconds=3.5)

    assert provider.base_url == "https://example.test/router"
    assert provider.timeout_seconds == 3.5


def test_osrm_provider_caches_identical_table_requests(monkeypatch):
    calls = []

    class FakeResponse:
        def read(self):
            return b'{"code":"Ok","distances":[[0,100],[100,0]],"durations":[[0,10],[10,0]]}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse()

    monkeypatch.setattr("otimizer_importer.routing.urlopen", fake_urlopen)
    provider = OSRMRoutingProvider(base_url="https://example.test/router", cache_entries=2)
    locations = [RouteEndpoint(-16.70, -49.20, "a"), RouteEndpoint(-16.71, -49.21, "b")]

    first = provider.table(locations)
    second = provider.table(locations)

    assert first == second
    assert len(calls) == 1


def test_osrm_provider_cache_is_bounded_lru(monkeypatch):
    calls = []

    class FakeResponse:
        def read(self):
            return b'{"code":"Ok","distances":[[0]],"durations":[[0]]}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr("otimizer_importer.routing.urlopen", fake_urlopen)
    provider = OSRMRoutingProvider(base_url="https://example.test/router", cache_entries=1)
    first = [RouteEndpoint(-16.70, -49.20, "a")]
    second = [RouteEndpoint(-16.71, -49.21, "b")]

    provider.table(first)
    provider.table(second)
    provider.table(first)

    assert len(calls) == 3


def test_provider_receives_endpoints_and_stops_in_route_matrix_order():
    matrix = tuple(tuple(TravelMetric(0, 0) for _ in range(3)) for _ in range(3))
    provider = FakeRoutingProvider(matrix)

    origin = RouteEndpoint(-16.70, -49.20, id="origin")
    destination = RouteEndpoint(-16.73, -49.23, id="destination")
    stops = [make_stop(0), make_stop(1)]

    result = build_route_matrix(stops, origin, destination, provider=provider)

    assert len(result) == 4
    assert all(len(row) == 4 for row in result)
    assert [location.id for location in provider.locations] == ["origin", "stop-1", "destination"]
    assert result[0][1] == TravelMetric(0, 0)
    assert result[1][0] == TravelMetric(0, 0)
