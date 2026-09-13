import pytest

from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import (
    OptimizationObjective,
    OptimizationProblem,
    RouteEndpoint,
    optimize,
)
from otimizer_importer.optimizer import OptimizationError
from otimizer_importer.routing import TravelMetric


def make_stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=-16.70 - index * 0.001,
        longitude=-49.20 - index * 0.001,
        deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, -16.70, -49.20)],
    )


def test_from_full_matrix_splits_origin_stops_and_destination():
    stops = (make_stop(0), make_stop(1))
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    destination = RouteEndpoint(-16.73, -49.23, "final")
    matrix = (
        (TravelMetric(0, 0), TravelMetric(10, 1), TravelMetric(20, 2), TravelMetric(30, 3)),
        (TravelMetric(11, 1), TravelMetric(0, 0), TravelMetric(40, 4), TravelMetric(50, 5)),
        (TravelMetric(21, 2), TravelMetric(41, 4), TravelMetric(0, 0), TravelMetric(60, 6)),
        (TravelMetric(31, 3), TravelMetric(51, 5), TravelMetric(61, 6), TravelMetric(0, 0)),
    )

    problem = OptimizationProblem.from_full_matrix(stops, matrix, origin=origin, destination=destination)

    assert problem.matrix == (
        (TravelMetric(0, 0), TravelMetric(40, 4)),
        (TravelMetric(41, 4), TravelMetric(0, 0)),
    )
    assert problem.origin_metrics == (TravelMetric(10, 1), TravelMetric(20, 2))
    assert problem.destination_metrics == (TravelMetric(50, 5), TravelMetric(60, 6))


def test_destination_changes_exact_route_selection():
    stops = (make_stop(0), make_stop(1), make_stop(2))
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    destination = RouteEndpoint(-16.75, -49.25, "final")
    matrix = (
        # depot, stop0, stop1, stop2, final
        (TravelMetric(0, 0), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(99, 99)),
        (TravelMetric(1, 1), TravelMetric(0, 0), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(100, 100)),
        (TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(0, 0), TravelMetric(1, 1), TravelMetric(100, 100)),
        (TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(0, 0), TravelMetric(1, 1)),
        (TravelMetric(99, 99), TravelMetric(100, 100), TravelMetric(100, 100), TravelMetric(1, 1), TravelMetric(0, 0)),
    )

    result = optimize(
        OptimizationProblem.from_full_matrix(
            stops,
            matrix,
            origin=origin,
            destination=destination,
            objective=OptimizationObjective.TIME,
        )
    )

    assert [stop.id for stop in result.route.stops] == ["stop-0", "stop-1", "stop-2"]
    assert result.origin_metric == TravelMetric(1, 1)
    assert result.destination_metric == TravelMetric(1, 1)
    assert result.route.delivery_count == 3


def test_full_matrix_rejects_wrong_size():
    stops = (make_stop(0),)
    with pytest.raises(ValueError, match="Full routing matrix size"):
        OptimizationProblem.from_full_matrix(stops, ((TravelMetric(0, 0),),))


def test_endpoint_constraints_reject_incomplete_route():
    stops = (make_stop(0), make_stop(1))
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    destination = RouteEndpoint(-16.73, -49.23, "final")
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1, 1), None, TravelMetric(1, 1)),
        (TravelMetric(1, 1), TravelMetric(0, 0), None, TravelMetric(1, 1)),
        (None, None, TravelMetric(0, 0), None),
        (TravelMetric(1, 1), TravelMetric(1, 1), None, TravelMetric(0, 0)),
    )

    with pytest.raises(OptimizationError, match="complete road-network route"):
        optimize(OptimizationProblem.from_full_matrix(stops, matrix, origin=origin, destination=destination))
