from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import OptimizationProblem, _two_opt
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


def test_two_opt_can_reorder_final_stop_on_open_route():
    stops = tuple(make_stop(index) for index in range(13))
    matrix = [[TravelMetric(100, 100) for _ in stops] for _ in stops]

    matrix[0][1] = TravelMetric(10, 10)
    for index in range(1, 12):
        matrix[index][index + 1] = TravelMetric(10, 10)
    matrix[0][12] = TravelMetric(1, 1)
    for index in range(2, 13):
        matrix[index][index - 1] = TravelMetric(1, 1)

    problem = OptimizationProblem(tuple(stops), tuple(tuple(row) for row in matrix))
    initial = tuple(range(13))

    optimized = _two_opt(initial, problem)

    assert optimized == (0, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1)
