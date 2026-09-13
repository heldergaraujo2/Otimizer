from dataclasses import dataclass

from .models import PhysicalStop, Route
from .routing import TravelMetric


@dataclass(frozen=True)
class RouteLeg:
    """One road-network leg represented in the final route result."""

    from_id: str
    to_id: str
    distance_meters: float
    duration_seconds: float


@dataclass(frozen=True)
class RouteMetrics:
    """Aggregated road-network metrics and individual legs for an ordered route."""

    distance_meters: float
    duration_seconds: float
    legs: tuple[RouteLeg, ...] = ()


def _leg(from_id: str, to_id: str, metric: TravelMetric) -> RouteLeg:
    return RouteLeg(from_id, to_id, metric.distance_meters, metric.duration_seconds)


def calculate_route_metrics(
    route: Route,
    physical_stops: list[PhysicalStop],
    matrix: tuple[tuple[TravelMetric | None, ...], ...],
    *,
    return_to_start: bool = False,
    origin_id: str | None = None,
    origin_metric: TravelMetric | None = None,
    destination_id: str | None = None,
    destination_metric: TravelMetric | None = None,
) -> RouteMetrics:
    """Calculate route legs and totals from the exact road-network matrix."""
    if len(matrix) != len(physical_stops) or any(len(row) != len(physical_stops) for row in matrix):
        raise ValueError("Routing matrix size must match physical stops")
    source_index = {stop.id: index for index, stop in enumerate(physical_stops)}
    if len(source_index) != len(physical_stops):
        raise ValueError("Physical stop IDs must be unique")
    if {stop.id for stop in route.stops} != set(source_index):
        raise ValueError("Route stops must match the routed physical stops")
    if origin_id is not None and origin_metric is None:
        raise ValueError("Origin metric is required when origin_id is provided")
    if destination_id is not None and destination_metric is None:
        raise ValueError("Destination metric is required when destination_id is provided")
    if origin_metric is not None and origin_id is None:
        raise ValueError("origin_id is required when origin metric is provided")
    if destination_metric is not None and destination_id is None:
        raise ValueError("destination_id is required when destination metric is provided")

    if route.physical_stop_count == 0:
        if origin_metric is not None or destination_metric is not None:
            raise ValueError("Endpoint metrics cannot be used with an empty route")
        return RouteMetrics(0.0, 0.0, ())

    legs: list[RouteLeg] = []
    distance = 0.0
    duration = 0.0

    if origin_metric is not None:
        first_id = route.stops[0].id
        legs.append(_leg(origin_id, first_id, origin_metric))
        distance += origin_metric.distance_meters
        duration += origin_metric.duration_seconds

    for current, following in zip(route.stops, route.stops[1:]):
        metric = matrix[source_index[current.id]][source_index[following.id]]
        if metric is None:
            raise ValueError(f"Route contains an unreachable leg: {current.id} -> {following.id}")
        legs.append(_leg(current.id, following.id, metric))
        distance += metric.distance_meters
        duration += metric.duration_seconds

    if destination_metric is not None:
        last_id = route.stops[-1].id
        legs.append(_leg(last_id, destination_id, destination_metric))
        distance += destination_metric.distance_meters
        duration += destination_metric.duration_seconds
    elif return_to_start:
        last_id = route.stops[-1].id
        first_id = route.stops[0].id
        metric = matrix[source_index[last_id]][source_index[first_id]]
        if metric is None:
            raise ValueError("Route cannot return to its starting stop")
        legs.append(_leg(last_id, first_id, metric))
        distance += metric.distance_meters
        duration += metric.duration_seconds

    return RouteMetrics(distance, duration, tuple(legs))


__all__ = ["RouteLeg", "RouteMetrics", "calculate_route_metrics"]
