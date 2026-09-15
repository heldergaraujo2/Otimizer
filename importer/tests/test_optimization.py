import pytest

from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import OptimizationObjective, OptimizationProblem, RouteEndpoint, optimize
from otimizer_importer.routing import TravelMetric


def make_stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}", latitude=-16.70 - index * 0.001, longitude=-49.20 - index * 0.001,
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
    assert problem.matrix == ((TravelMetric(0, 0), TravelMetric(40, 4)), (TravelMetric(41, 4), TravelMetric(0, 0)))
    assert problem.origin_metrics == (TravelMetric(10, 1), TravelMetric(20, 2))
    assert problem.destination_metrics == (TravelMetric(50, 5), TravelMetric(60, 6))


def test_destination_changes_exact_route_selection():
    stops = (make_stop(0), make_stop(1), make_stop(2))
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    destination = RouteEndpoint(-16.75, -49.25, "final")
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(99, 99)),
        (TravelMetric(1, 1), TravelMetric(0, 0), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(100, 100)),
        (TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(0, 0), TravelMetric(1, 1), TravelMetric(100, 100)),
        (TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(1, 1), TravelMetric(0, 0), TravelMetric(1, 1)),
        (TravelMetric(99, 99), TravelMetric(100, 100), TravelMetric(100, 100), TravelMetric(1, 1), TravelMetric(0, 0)),
    )
    result = optimize(OptimizationProblem.from_full_matrix(stops, matrix, origin=origin, destination=destination, objective=OptimizationObjective.TIME))
    assert [stop.id for stop in result.route.stops] == ["stop-0", "stop-1", "stop-2"]
    assert result.origin_metric == TravelMetric(1, 1)
    assert result.destination_metric == TravelMetric(1, 1)
    assert result.route.delivery_count == 3


def test_full_matrix_rejects_wrong_size_when_origin_is_declared():
    stops = (make_stop(0),)
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    with pytest.raises(ValueError, match="Full routing matrix size"):
        OptimizationProblem.from_full_matrix(stops, ((TravelMetric(0, 0),),), origin=origin)


def test_unreachable_stop_does_not_abort_route_optimization():
    stops = (make_stop(0), make_stop(1), make_stop(2))
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1, 1), None),
        (TravelMetric(1, 1), TravelMetric(0, 0), None),
        (None, None, TravelMetric(0, 0)),
    )
    result = optimize(OptimizationProblem.from_full_matrix(stops, matrix))
    assert [stop.id for stop in result.route.stops] == ["stop-0", "stop-1", "stop-2"]
    assert result.route.delivery_count == 3


def test_large_route_with_one_unreachable_stop_keeps_all_deliveries():
    size = 100
    isolated = 99
    stops = tuple(make_stop(index) for index in range(size))
    matrix = tuple(
        tuple(TravelMetric(0, 0) if row == column else None if row == isolated or column == isolated else TravelMetric(1, 1) for column in range(size))
        for row in range(size)
    )
    result = optimize(OptimizationProblem.from_full_matrix(stops, matrix))
    assert len(result.route.stops) == size
    assert {stop.id for stop in result.route.stops} == {f"stop-{index}" for index in range(size)}
    assert result.route.delivery_count == size


def test_best_effort_keeps_minimum_missing_legs_before_cost_on_11_stops():
    size = 11
    stops = tuple(make_stop(index) for index in range(size))
    matrix = [[TravelMetric(0, 0) if row == column else TravelMetric(50, 50) for column in range(size)] for row in range(size)]
    for index in range(size - 1):
        matrix[index][index + 1] = TravelMetric(10, 10)
    matrix[1][10] = TravelMetric(1, 1)
    matrix[10][2] = TravelMetric(100, 100)
    destination = RouteEndpoint(-16.80, -49.30, "final")
    destination_metrics = tuple(None for _ in range(size))
    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        destination=destination,
        destination_metrics=destination_metrics,
    )

    result = optimize(problem)

    assert [stop.id for stop in result.route.stops] == [f"stop-{index}" for index in range(size)]
    assert result.destination_metric is None
    assert result.route.delivery_count == size
