from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import OptimizationObjective, OptimizationProblem, RouteEndpoint, optimize
from otimizer_importer.routing import TravelMetric


def make_stops(count: int) -> tuple[PhysicalStop, ...]:
    return tuple(
        PhysicalStop(
            id=f"stop-{index}",
            latitude=-16.70 - index * 0.001,
            longitude=-49.20 - index * 0.001,
            deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", None, None, None, None, -16.70, -49.20)],
        )
        for index in range(count)
    )


def metric(value: float) -> TravelMetric:
    return TravelMetric(distance_meters=value, duration_seconds=value)


def test_large_route_uses_2opt_to_improve_greedy_order():
    stops = make_stops(13)
    size = len(stops)
    matrix = [[metric(1000) for _ in range(size)] for _ in range(size)]
    for index in range(size):
        matrix[index][index] = metric(0)

    # The first four stops intentionally make nearest-neighbor choose
    # 0 -> 1 -> 2 -> 3, while reversing [1, 2] produces a much cheaper
    # 0 -> 2 -> 1 -> 3 route. Remaining stops form a cheap chain.
    matrix[0][1] = metric(1)
    matrix[0][2] = metric(2)
    matrix[1][2] = metric(1)
    matrix[1][3] = metric(2)
    matrix[2][3] = metric(10)
    matrix[2][1] = metric(1)
    matrix[1][3] = metric(2)
    matrix[3][4] = metric(1)
    for index in range(4, size - 1):
        matrix[index][index + 1] = metric(1)
    for row in range(size):
        for col in range(size):
            if row != col and matrix[row][col].distance_meters == 1000:
                matrix[row][col] = metric(100 + abs(row - col))

    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        objective=OptimizationObjective.DISTANCE,
    )
    result = optimize(problem)

    order = [stop.physical_stop.id for stop in result.route.stops]
    assert order[:4] == ["stop-0", "stop-2", "stop-1", "stop-3"]
    assert len(order) == 13
    assert len(set(order)) == 13


def test_2opt_preserves_external_destination_and_return_constraint():
    stops = make_stops(13)
    size = len(stops)
    destination = RouteEndpoint(-16.90, -49.40, "destination")
    matrix = [[metric(50) for _ in range(size + 1)] for _ in range(size + 1)]
    for index in range(size + 1):
        matrix[index][index] = metric(0)
    for index in range(size - 1):
        matrix[index][index + 1] = metric(1)
    for index in range(size):
        matrix[index][size] = metric(1 if index == size - 1 else 30)

    problem = OptimizationProblem.from_full_matrix(
        stops,
        tuple(tuple(row) for row in matrix),
        destination=destination,
        objective=OptimizationObjective.TIME,
    )
    result = optimize(problem)

    assert result.route.physical_stop_count == 13
    assert result.destination == destination
    assert result.destination_metric == metric(1)
    assert result.route.stops[0].sequence == 1
    assert result.route.stops[-1].sequence == 13
