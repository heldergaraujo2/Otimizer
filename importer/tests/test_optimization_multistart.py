from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import OptimizationObjective, OptimizationProblem, RouteEndpoint, optimize
from otimizer_importer.routing import TravelMetric


def stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=-16.70 - index * 0.001,
        longitude=-49.20 - index * 0.001,
        deliveries=[
            Delivery(
                index + 1, None, None, None, f"TN-{index}", None, None, None, None,
                -16.70, -49.20,
            )
        ],
    )


def dense_matrix(size: int, default: int = 1000) -> list[list[TravelMetric]]:
    return [
        [TravelMetric(0, 0) if row == col else TravelMetric(default, default) for col in range(size)]
        for row in range(size)
    ]


def test_large_origin_route_considers_multiple_start_candidates():
    stops = tuple(stop(index) for index in range(13))
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    size = len(stops)

    matrix = dense_matrix(size)

    # One complete low-cost cycle starts at 6. Starting at 0 is slightly
    # cheaper from the origin but leads greedy construction into an expensive
    # transition. Multi-start + 2-opt should discover the better basin.
    for left, right in zip(range(6, 12), range(7, 13)):
        matrix[left][right] = TravelMetric(1, 1)
    for left, right in zip(range(0, 5), range(1, 6)):
        matrix[left][right] = TravelMetric(1, 1)
    matrix[12][0] = TravelMetric(1, 1)

    origin_metrics = tuple(
        TravelMetric(1 if index == 0 else 2, 1 if index == 0 else 2)
        for index in range(size)
    )

    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        origin=origin,
        origin_metrics=origin_metrics,
        objective=OptimizationObjective.TIME,
    )

    result = optimize(problem)

    assert result.route.physical_stop_count == 13
    assert result.route.delivery_count == 13
    assert result.origin_metric == TravelMetric(2, 2)
    assert result.route.stops[0].id == "stop-6"


def test_large_route_with_destination_keeps_destination_metric():
    stops = tuple(stop(index) for index in range(13))
    size = len(stops)
    matrix = dense_matrix(size)
    destination = RouteEndpoint(-16.85, -49.25, "customer")

    # A cheap chain exercises insertion in the middle while the destination
    # costs make the final stop materially different from the nearest-neighbor
    # choice.
    for left, right in zip(range(0, 12), range(1, 13)):
        matrix[left][right] = TravelMetric(1, 1)
    destination_metrics = tuple(
        TravelMetric(2 if index == 12 else 500, 2 if index == 12 else 500)
        for index in range(size)
    )

    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        destination=destination,
        destination_metrics=destination_metrics,
        objective=OptimizationObjective.TIME,
    )

    result = optimize(problem)

    assert result.route.physical_stop_count == 13
    assert result.route.delivery_count == 13
    assert result.destination_metric == TravelMetric(2, 2)
    assert result.route.stops[-1].id == "stop-12"


def test_large_return_route_preserves_return_to_start_cost():
    stops = tuple(stop(index) for index in range(13))
    size = len(stops)
    matrix = dense_matrix(size)

    for left, right in zip(range(0, 12), range(1, 13)):
        matrix[left][right] = TravelMetric(1, 1)
    matrix[12][0] = TravelMetric(3, 3)

    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        return_to_start=True,
        objective=OptimizationObjective.TIME,
    )

    result = optimize(problem)

    assert result.route.physical_stop_count == 13
    assert result.route.delivery_count == 13
    assert result.return_to_start is True
    assert result.route.stops[0].id == "stop-0"


def test_large_sparse_route_falls_back_when_regret_insertion_is_infeasible():
    stops = tuple(stop(index) for index in range(13))
    size = len(stops)
    matrix = [[None] * size for _ in range(size)]
    for index in range(size):
        matrix[index][index] = TravelMetric(0, 0)

    # This directed road graph has one valid complete route for greedy
    # construction, while regret insertion can reach an intermediate partial
    # order with no feasible insertion. The optimizer must keep the valid
    # greedy seed instead of failing the entire optimization.
    sparse_edges = {
        (0, 1): 2,
        (0, 2): 2,
        (1, 0): 10,
        (1, 2): 10,
        (2, 0): 2,
        (2, 1): 3,
        (2, 3): 10,
        (3, 0): 10,
    }
    for index in range(3, size - 1):
        sparse_edges[index, index + 1] = 1
    for (left, right), cost in sparse_edges.items():
        matrix[left][right] = TravelMetric(cost, cost)

    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        objective=OptimizationObjective.TIME,
    )

    result = optimize(problem)

    assert result.route.physical_stop_count == 13
    assert result.route.delivery_count == 13
    assert [item.id for item in result.route.stops] == [f"stop-{index}" for index in range(13)]
