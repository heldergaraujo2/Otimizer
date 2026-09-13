from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import (
    OptimizationObjective,
    OptimizationProblem,
    RouteEndpoint,
    optimize,
)
from otimizer_importer.routing import TravelMetric


def make_stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=-16.70 - index * 0.001,
        longitude=-49.20 - index * 0.001,
        deliveries=[
            Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, -16.70, -49.20)
        ],
    )


def test_destination_participates_in_route_selection():
    stops = tuple(make_stop(index) for index in range(3))
    matrix = (
        (TravelMetric(0, 0), TravelMetric(10, 10), TravelMetric(1, 1)),
        (TravelMetric(10, 10), TravelMetric(0, 0), TravelMetric(100, 100)),
        (TravelMetric(1, 1), TravelMetric(100, 100), TravelMetric(0, 0)),
    )
    destination_metrics = (
        TravelMetric(50, 50),
        TravelMetric(1, 1),
        TravelMetric(100, 100),
    )

    result = optimize(
        OptimizationProblem(
            stops=stops,
            matrix=matrix,
            destination=RouteEndpoint(-16.8, -49.3, id="destination"),
            destination_metrics=destination_metrics,
        )
    )

    assert [item.id for item in result.route.stops] == ["stop-0", "stop-2", "stop-1"]
    assert result.destination_metric == TravelMetric(1, 1)
    assert result.route.physical_stop_count == 3
    assert result.route.delivery_count == 3


def test_origin_participates_in_start_selection():
    stops = tuple(make_stop(index) for index in range(2))
    matrix = (
        (TravelMetric(0, 0), TravelMetric(100, 100)),
        (TravelMetric(1, 1), TravelMetric(0, 0)),
    )
    origin_metrics = (TravelMetric(100, 100), TravelMetric(1, 1))

    result = optimize(
        OptimizationProblem(
            stops=stops,
            matrix=matrix,
            origin=RouteEndpoint(-16.8, -49.3, id="depot"),
            origin_metrics=origin_metrics,
            objective=OptimizationObjective.TIME,
        )
    )

    assert [item.id for item in result.route.stops] == ["stop-1", "stop-0"]
    assert result.start_index is None
    assert result.origin_metric == TravelMetric(1, 1)


def test_endpoint_metrics_are_required_for_declared_endpoints():
    stops = tuple(make_stop(index) for index in range(2))
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1, 1)),
        (TravelMetric(1, 1), TravelMetric(0, 0)),
    )

    try:
        OptimizationProblem(
            stops=stops,
            matrix=matrix,
            origin=RouteEndpoint(-16.8, -49.3),
        )
    except ValueError as exc:
        assert "Origin metrics" in str(exc)
    else:
        raise AssertionError("Expected origin metrics validation")
