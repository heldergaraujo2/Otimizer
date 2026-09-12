from .models import PhysicalStop, Route
from .routing import TravelMetric


class OptimizationError(RuntimeError):
    """Raised when a complete road-network route cannot be produced."""


def optimize_nearest_neighbor(
    stops: list[PhysicalStop],
    matrix: tuple[tuple[TravelMetric | None, ...], ...],
    *,
    start_index: int = 0,
    return_to_start: bool = False,
) -> Route:
    """Build a complete route using road-network travel time as the greedy cost.

    This is deliberately a deterministic first optimizer. It never uses source
    Sequence/Stop values and refuses to silently omit an unreachable physical stop.
    """
    size = len(stops)
    if size == 0:
        return Route.from_physical_stops([])
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise OptimizationError("Routing matrix size must match physical stops")
    if not 0 <= start_index < size:
        raise OptimizationError("start_index is outside the physical-stop list")

    remaining = set(range(size))
    order = [start_index]
    remaining.remove(start_index)
    current = start_index

    while remaining:
        candidates = [index for index in remaining if matrix[current][index] is not None]
        if not candidates:
            raise OptimizationError("No road-network path reaches all physical stops")
        next_index = min(
            candidates,
            key=lambda index: (
                matrix[current][index].duration_seconds,
                matrix[current][index].distance_meters,
                index,
            ),
        )
        order.append(next_index)
        remaining.remove(next_index)
        current = next_index

    if return_to_start and matrix[current][start_index] is None:
        raise OptimizationError("Route cannot return to its starting physical stop")

    return Route.from_physical_stops([stops[index] for index in order])
