from dataclasses import dataclass

from .models import PhysicalStop, Route
from .routing import TravelMetric


@dataclass(frozen=True)
class RouteMetrics:
    """Aggregated road-network metrics for an ordered route."""

    distance_meters: float
    duration_seconds: float


def calculate_route_metrics(
    route: Route,
    physical_stops: list[PhysicalStop],
    matrix: tuple[tuple[TravelMetric | None, ...], ...],
    *,
    return_to_start: bool = False,
) -> RouteMetrics:
    """Sum road-network distance and duration for every route leg.

    ``matrix`` uses the same physical-stop ordering supplied by the routing
    provider, while ``route`` contains that same set in optimized order.
    """
    if len(matrix) != len(physical_stops) or any(len(row) != len(physical_stops) for row in matrix):
        raise ValueError("Routing matrix size must match physical stops")
    source_index = {stop.id: index for index, stop in enumerate(physical_stops)}
    if len(source_index) != len(physical_stops):
        raise ValueError("Physical stop IDs must be unique")
    if {stop.id for stop in route.stops} != set(source_index):
        raise ValueError("Route stops must match the routed physical stops")

    if route.physical_stop_count <= 1:
        if return_to_start and route.physical_stop_count == 1:
            index = source_index[route.stops[0].id]
            metric = matrix[index][index]
            if metric is None:
                raise ValueError("Route cannot return to its starting stop")
            return RouteMetrics(metric.distance_meters, metric.duration_seconds)
        return RouteMetrics(0.0, 0.0)

    distance = 0.0
    duration = 0.0
    for current, following in zip(route.stops, route.stops[1:]):
        current_index = source_index[current.id]
        following_index = source_index[following.id]
        metric = matrix[current_index][following_index]
        if metric is None:
            raise ValueError(f"Route contains an unreachable leg: {current.id} -> {following.id}")
        distance += metric.distance_meters
        duration += metric.duration_seconds

    if return_to_start:
        last_index = source_index[route.stops[-1].id]
        first_index = source_index[route.stops[0].id]
        metric = matrix[last_index][first_index]
        if metric is None:
            raise ValueError("Route cannot return to its starting stop")
        distance += metric.distance_meters
        duration += metric.duration_seconds

    return RouteMetrics(distance, duration)
