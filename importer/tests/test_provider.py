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


def test_provider_receives_endpoints_and_stops_in_route_matrix_order():
    matrix = tuple(tuple(TravelMetric(0, 0) for _ in range(4)) for _ in range(4))
    provider = FakeRoutingProvider(matrix)

    origin = RouteEndpoint(-16.70, -49.20, id="origin")
    destination = RouteEndpoint(-16.73, -49.23, id="destination")
    stops = [make_stop(0), make_stop(1)]

    result = build_route_matrix(stops, origin, destination, provider=provider)

    assert result == matrix
    assert [location.id for location in provider.locations] == ["origin", "stop-0", "stop-1", "destination"]
