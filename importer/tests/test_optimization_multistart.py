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


def test_large_origin_route_considers_multiple_start_candidates():
    stops = tuple(stop(index) for index in range(13))
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    size = len(stops)

    matrix = []
    for row in range(size):
        values = []
        for col in range(size):
            values.append(TravelMetric(0, 0) if row == col else TravelMetric(1000 + abs(row - col), 1000 + abs(row - col)))
        matrix.append(values)

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
