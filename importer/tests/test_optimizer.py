import pytest

from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimizer import OptimizationError, optimize_nearest_neighbor
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


def test_optimizer_uses_road_metric_and_preserves_every_stop():
    stops = [make_stop(0), make_stop(1), make_stop(2)]
    matrix = (
        (TravelMetric(0, 0), TravelMetric(1000, 300), TravelMetric(500, 600)),
        (TravelMetric(1000, 300), TravelMetric(0, 0), TravelMetric(700, 200)),
        (TravelMetric(500, 600), TravelMetric(700, 200), TravelMetric(0, 0)),
    )

    route = optimize_nearest_neighbor(stops, matrix)

    assert [item.id for item in route.stops] == ["stop-0", "stop-1", "stop-2"]
    assert route.physical_stop_count == 3
    assert route.delivery_count == 3


def test_optimizer_does_not_use_straight_line_or_source_sequence():
    stops = [make_stop(0), make_stop(1), make_stop(2)]
    matrix = (
        (TravelMetric(0, 0), TravelMetric(900, 100), TravelMetric(100, 500)),
        (TravelMetric(900, 100), TravelMetric(0, 0), TravelMetric(800, 50)),
        (TravelMetric(100, 500), TravelMetric(800, 50), TravelMetric(0, 0)),
    )

    route = optimize_nearest_neighbor(stops, matrix)

    assert [item.id for item in route.stops] == ["stop-0", "stop-2", "stop-1"]


def test_optimizer_rejects_unreachable_remaining_stop():
    stops = [make_stop(0), make_stop(1)]
    matrix = ((TravelMetric(0, 0), None), (None, TravelMetric(0, 0)))

    with pytest.raises(OptimizationError, match="reaches all"):
        optimize_nearest_neighbor(stops, matrix)


def test_optimizer_can_require_return_to_start():
    stops = [make_stop(0), make_stop(1)]
    matrix = ((TravelMetric(0, 0), TravelMetric(1000, 100)), (None, TravelMetric(0, 0)))

    with pytest.raises(OptimizationError, match="return"):
        optimize_nearest_neighbor(stops, matrix, return_to_start=True)
