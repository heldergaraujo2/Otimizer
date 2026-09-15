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
    assert [(leg.from_id, leg.to_id) for leg in metrics.legs] == [("stop-0", "stop-2"), ("stop-2", "stop-1")]
    assert sum(leg.distance_meters for leg in metrics.legs) == metrics.distance_meters
    assert sum(leg.duration_seconds for leg in metrics.legs) == metrics.duration_seconds


def test_route_metrics_can_include_origin_and_destination_legs():
    stops = [make_stop(0), make_stop(1)]
    matrix = ((TravelMetric(0, 0), TravelMetric(1000, 100)), (TravelMetric(1100, 110), TravelMetric(0, 0)))
    route = Route.from_physical_stops(stops)
    metrics = calculate_route_metrics(route, stops, matrix, origin_id="depot", origin_metric=TravelMetric(700, 70), destination_id="final", destination_metric=TravelMetric(900, 90))
    assert metrics.distance_meters == 2600
    assert metrics.duration_seconds == 260
    assert [(leg.from_id, leg.to_id) for leg in metrics.legs] == [("depot", "stop-0"), ("stop-0", "stop-1"), ("stop-1", "final")]


def test_route_metrics_can_include_return_leg():
    stops = [make_stop(0), make_stop(1)]
    matrix = ((TravelMetric(0, 0), TravelMetric(1000, 100)), (TravelMetric(1200, 120), TravelMetric(0, 0)))
    route = Route.from_physical_stops(stops)
    metrics = calculate_route_metrics(route, stops, matrix, return_to_start=True)
    assert metrics.distance_meters == 2200
    assert metrics.duration_seconds == 220
    assert [(leg.from_id, leg.to_id) for leg in metrics.legs] == [("stop-0", "stop-1"), ("stop-1", "stop-0")]


def test_unroutable_leg_is_reported_without_failing_metrics():
    stops = [make_stop(0), make_stop(1), make_stop(2)]
    route = Route.from_physical_stops(stops)
    matrix = (
        (TravelMetric(0, 0), TravelMetric(10, 1), None),
        (TravelMetric(10, 1), TravelMetric(0, 0), None),
        (None, None, TravelMetric(0, 0)),
    )
    metrics = calculate_route_metrics(route, stops, matrix)
    assert metrics.distance_meters == 10
    assert metrics.duration_seconds == 1
    assert metrics.unroutable_legs == 1
    assert metrics.routing_complete is False
    assert metrics.legs[-1].routable is False
    assert metrics.legs[-1].distance_meters is None
    assert metrics.legs[-1].duration_seconds is None


def test_unroutable_return_leg_is_reported_without_failing_metrics():
    stops = [make_stop(0), make_stop(1)]
    route = Route.from_physical_stops(stops)
    matrix = ((TravelMetric(0, 0), TravelMetric(10, 1)), (None, TravelMetric(0, 0)))
    metrics = calculate_route_metrics(route, stops, matrix, return_to_start=True)
    assert metrics.routing_complete is False
    assert metrics.legs[-1].from_id == "stop-1"
    assert metrics.legs[-1].to_id == "stop-0"
    assert metrics.legs[-1].routable is False
