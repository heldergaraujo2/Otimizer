from dataclasses import dataclass

from .models import PhysicalStop, Route
from .routing import TravelMetric


@dataclass(frozen=True)
class RouteLeg:
    """One road-network leg represented in the final route result."""

    from_id: str
    to_id: str
    distance_meters: float | None
    duration_seconds: float | None
    routable: bool = True


@dataclass(frozen=True)
class RouteMetrics:
    """Aggregated road-network metrics and individual legs for an ordered route."""

    distance_meters: float
    duration_seconds: float
    legs: tuple[RouteLeg, ...] = ()

    @property
    def unroutable_legs(self) -> int:
        return sum(not leg.routable for leg in self.legs)

    @property
    def routing_complete(self) -> bool:
        return self.unroutable_legs == 0


def _leg(from_id: str, to_id: str, metric: TravelMetric | None) -> RouteLeg:
    if metric is None:
        return RouteLeg(from_id, to_id, None, None, False)
    return RouteLeg(from_id, to_id, metric.distance_meters, metric.duration_seconds, True)


def _add_metric_totals(distance: float, duration: float, metric: TravelMetric | None) -> tuple[float, float]:
    if metric is None:
        return distance, duration
    return distance + metric.distance_meters, duration + metric.duration_seconds


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
    """Calculate route legs without turning one unavailable road leg into a fatal error."""
    if len(matrix) != len(physical_stops) or any(len(row) != len(physical_stops) for row in matrix):
        raise ValueError("Routing matrix size must match physical stops")
    source_index = {stop.id: index for index, stop in enumerate(physical_stops)}
    if len(source_index) != len(physical_stops):
        raise ValueError("Physical stop IDs must be unique")
    if origin_id is not None and origin_metric is not None and route.physical_stop_count == 0:
        raise ValueError("Endpoint metrics cannot be used with an empty route")
    if destination_id is not None and route.physical_stop_count == 0:
        raise ValueError("Endpoint metrics cannot be used with an empty route")
    if origin_metric is not None and origin_id is None:
        raise ValueError("origin_id is required when origin metric is provided")
    if destination_metric is not None and destination_id is None:
        raise ValueError("destination_id is required when destination metric is provided")
    if origin_id is not None and origin_metric is None and route.physical_stop_count == 0:
        raise ValueError("Endpoint metrics cannot be used with an empty route")
    if destination_id is not None and destination_metric is None and route.physical_stop_count == 0:
        raise ValueError("Endpoint metrics cannot be used with an empty route")

    if route.physical_stop_count == 0:
        return RouteMetrics(0.0, 0.0, ())

    if {stop.id for stop in route.stops} != set(source_index):
        raise ValueError("Route stops must match the routed physical stops")

    legs: list[RouteLeg] = []
    distance = 0.0
    duration = 0.0

    if origin_id is not None:
        first_id = route.stops[0].id
        legs.append(_leg(origin_id, first_id, origin_metric))
        distance, duration = _add_metric_totals(distance, duration, origin_metric)

    for current, following in zip(route.stops, route.stops[1:]):
        metric = matrix[source_index[current.id]][source_index[following.id]]
        legs.append(_leg(current.id, following.id, metric))
        distance, duration = _add_metric_totals(distance, duration, metric)

    if destination_id is not None:
        last_id = route.stops[-1].id
        legs.append(_leg(last_id, destination_id, destination_metric))
        distance, duration = _add_metric_totals(distance, duration, destination_metric)
    elif return_to_start:
        last_id = route.stops[-1].id
        first_id = route.stops[0].id
        metric = matrix[source_index[last_id]][source_index[first_id]]
        legs.append(_leg(last_id, first_id, metric))
        distance, duration = _add_metric_totals(distance, duration, metric)

    return RouteMetrics(distance, duration, tuple(legs))


__all__ = ["RouteLeg", "RouteMetrics", "calculate_route_metrics"]
