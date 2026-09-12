from dataclasses import dataclass

from .models import Route
from .routing import TravelMetric


@dataclass(frozen=True)
class RouteMetrics:
    """Aggregated road-network metrics for an ordered route."""

    distance_meters: float
    duration_seconds: float


def calculate_route_metrics(
    route: Route,
    matrix: tuple[tuple[TravelMetric | None, ...], ...],
    *,
    return_to_start: bool = False,
) -> RouteMetrics:
    """Sum road-network distance and duration for every route leg.

    The matrix is indexed by the physical-stop order used to build it. Route
    stops must therefore be identifiable in the supplied ``stops`` sequence.
    """
    if route.physical_stop_count <= 1:
        if return_to_start and route.physical_stop_count == 1:
            raise ValueError("A return leg requires the route matrix stop index")
        return RouteMetrics(0.0, 0.0)

    ids = [stop.id for stop in route.stops]
    index_by_id: dict[str, int] = {}
    for index, stop_id in enumerate(ids):
        index_by_id[stop_id] = index

    distance = 0.0
    duration = 0.0
    for current, following in zip(route.stops, route.stops[1:]):
        current_index = index_by_id[current.id]
        following_index = index_by_id[following.id]
        if current_index >= len(matrix) or following_index >= len(matrix):
            raise ValueError("Routing matrix is smaller than the route")
        metric = matrix[current_index][following_index]
        if metric is None:
            raise ValueError(f"Route contains an unreachable leg: {current.id} -> {following.id}")
        distance += metric.distance_meters
        duration += metric.duration_seconds

    if return_to_start:
        first_index = index_by_id[route.stops[0].id]
        last_index = index_by_id[route.stops[-1].id]
        if last_index >= len(matrix) or first_index >= len(matrix):
            raise ValueError("Routing matrix is smaller than the route")
        metric = matrix[last_index][first_index]
        if metric is None:
            raise ValueError("Route cannot return to its starting stop")
        distance += metric.distance_meters
        duration += metric.duration_seconds

    return RouteMetrics(distance, duration)
