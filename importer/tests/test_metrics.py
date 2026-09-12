import pytest

from otimizer_importer.metrics import calculate_route_metrics
from otimizer_importer.models import Delivery, PhysicalStop, Route
from otimizer_importer.routing import TravelMetric


def make_stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=-16.7 - index * 0.001,
        longitude=-49.2 - index * 0.001,
        deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, -16.7, -49.2)],
    )


def test_route_metrics_follow_optimized_order_against_original_matrix_order():
    stops = [make_stop(0), make_stop(1), make_stop(2)]
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1000, 100), TravelMetric(5000, 500)),
        (TravelMetric(1100, 110), TravelMetric(0, 0), TravelMetric(2000, 200)),
        (TravelMetric(5100, 510), TravelMetric(2100, 210), TravelMetric(0, 0)),
    )
    route = Route.from_physical_stops([stops[0], stops[2], stops[1]])

    metrics = calculate_route_metrics(route, stops, matrix)

    assert metrics.distance_meters == 7100
    assert metrics.duration_seconds == 710


def test_route_metrics_can_include_return_leg():
    stops = [make_stop(0), make_stop(1)]
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1000, 100)),
        (TravelMetric(1200, 120), TravelMetric(0, 0)),
    )
    route = Route.from_physical_stops(stops)

    metrics = calculate_route_metrics(route, stops, matrix, return_to_start=True)

    assert metrics.distance_meters == 2200
    assert metrics.duration_seconds == 220


def test_route_metrics_rejects_unreachable_leg():
    stops = [make_stop(0), make_stop(1)]
    matrix = (
        (TravelMetric(0, 0), None),
        (TravelMetric(1000, 100), TravelMetric(0, 0)),
    )
    route = Route.from_physical_stops(stops)

    with pytest.raises(ValueError, match="unreachable leg"):
        calculate_route_metrics(route, stops, matrix)
