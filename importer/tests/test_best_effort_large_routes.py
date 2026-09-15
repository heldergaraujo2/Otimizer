from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import OptimizationProblem, RouteEndpoint, optimize
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


def test_large_best_effort_minimizes_missing_legs_before_greedy_edge_cost():
    size = 13
    stops = tuple(make_stop(index) for index in range(size))
    matrix = [[None for _ in range(size)] for _ in range(size)]
    for index in range(size):
        matrix[index][index] = TravelMetric(0, 0)
    for index in range(size - 1):
        matrix[index][index + 1] = TravelMetric(10, 10)
    matrix[0][12] = TravelMetric(1, 1)

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


def test_over_14_best_effort_does_not_trade_missing_legs_for_a_cheap_greedy_edge():
    size = 15
    stops = tuple(make_stop(index) for index in range(size))
    matrix = [[None for _ in range(size)] for _ in range(size)]
    for index in range(size):
        matrix[index][index] = TravelMetric(0, 0)
    for index in range(size - 1):
        matrix[index][index + 1] = TravelMetric(10, 10)
    matrix[0][14] = TravelMetric(1, 1)

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
