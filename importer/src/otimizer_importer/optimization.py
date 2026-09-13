from dataclasses import dataclass
from enum import Enum

from .models import PhysicalStop, Route
from .optimizer import OptimizationError, optimize_nearest_neighbor
from .routing import TravelMetric


class OptimizationObjective(str, Enum):
    """Primary metric used when selecting the next physical stop."""

    TIME = "time"
    DISTANCE = "distance"


@dataclass(frozen=True)
class RouteEndpoint:
    """A fixed geographic endpoint, such as a depot or final destination."""

    latitude: float
    longitude: float
    id: str = "endpoint"


@dataclass(frozen=True)
class OptimizationProblem:
    """Configuration for producing a complete optimized physical-stop route."""

    stops: tuple[PhysicalStop, ...]
    matrix: tuple[tuple[TravelMetric | None, ...], ...]
    start_index: int = 0
    return_to_start: bool = False
    objective: OptimizationObjective = OptimizationObjective.TIME
    origin: RouteEndpoint | None = None
    destination: RouteEndpoint | None = None
    origin_metrics: tuple[TravelMetric | None, ...] | None = None
    destination_metrics: tuple[TravelMetric | None, ...] | None = None

    def __post_init__(self) -> None:
        size = len(self.stops)
        if len(self.matrix) != size or any(len(row) != size for row in self.matrix):
            raise ValueError("Routing matrix size must match physical stops")
        if size and not 0 <= self.start_index < size:
            raise ValueError("start_index is outside the physical-stop list")
        if len({stop.id for stop in self.stops}) != size:
            raise ValueError("Physical stop IDs must be unique")
        if self.origin is not None:
            if self.origin_metrics is None or len(self.origin_metrics) != size:
                raise ValueError("Origin metrics must contain one value per physical stop")
        elif self.origin_metrics is not None:
            raise ValueError("Origin metrics require an origin endpoint")
        if self.destination is not None:
            if self.destination_metrics is None or len(self.destination_metrics) != size:
                raise ValueError("Destination metrics must contain one value per physical stop")
        elif self.destination_metrics is not None:
            raise ValueError("Destination metrics require a destination endpoint")
        if self.origin is not None and self.return_to_start:
            raise ValueError("Use either an origin endpoint or return_to_start, not both")


@dataclass(frozen=True)
class OptimizationResult:
    """Result containing the ordered route and the configuration used."""

    route: Route
    objective: OptimizationObjective
    start_index: int | None
    return_to_start: bool
    origin: RouteEndpoint | None = None
    destination: RouteEndpoint | None = None
    origin_metric: TravelMetric | None = None
    destination_metric: TravelMetric | None = None


def _metric_cost(metric: TravelMetric, objective: OptimizationObjective) -> tuple[float, float]:
    if objective == OptimizationObjective.DISTANCE:
        return metric.distance_meters, metric.duration_seconds
    return metric.duration_seconds, metric.distance_meters


def _empty_result(problem: OptimizationProblem) -> OptimizationResult:
    return OptimizationResult(Route.from_physical_stops([]), problem.objective, None, False, problem.origin, problem.destination)


def optimize(problem: OptimizationProblem) -> OptimizationResult:
    """Run the baseline optimizer with explicit endpoints.

    External endpoints are not deliveries and therefore never receive a route
    sequence. Their road-network metrics are retained in the result so a caller
    can report the complete trip, including origin-to-first-stop and last-stop-to-
    destination legs.
    """
    if not problem.stops:
        return _empty_result(problem)

    if problem.origin is None:
        route = optimize_nearest_neighbor(
            list(problem.stops), problem.matrix,
            start_index=problem.start_index,
            return_to_start=problem.return_to_start,
            objective=problem.objective,
        )
        destination_metric = None
        if problem.destination is not None:
            destination_metric = problem.destination_metrics[route.stops[-1].physical_stop.id] if False else None
        return OptimizationResult(route, problem.objective, problem.start_index, problem.return_to_start,
                                  problem.origin, problem.destination, None, destination_metric)

    candidates = [index for index, metric in enumerate(problem.origin_metrics or ()) if metric is not None]
    if not candidates:
        raise OptimizationError("No road-network path reaches a physical stop from the origin")

    first = min(candidates, key=lambda index: (*_metric_cost(problem.origin_metrics[index], problem.objective), index))
    baseline = optimize_nearest_neighbor(
        list(problem.stops), problem.matrix,
        start_index=first,
        return_to_start=False,
        objective=problem.objective,
    )
    origin_metric = problem.origin_metrics[first]
    destination_metric = None
    if problem.destination is not None:
        last_index = next(index for index, stop in enumerate(problem.stops) if stop.id == baseline.stops[-1].id)
        destination_metric = problem.destination_metrics[last_index]
        if destination_metric is None:
            raise OptimizationError("Route cannot reach the destination from its final physical stop")

    return OptimizationResult(
        baseline, problem.objective, None, False,
        problem.origin, problem.destination, origin_metric, destination_metric,
    )


__all__ = [
    "OptimizationError",
    "OptimizationObjective",
    "OptimizationProblem",
    "OptimizationResult",
    "RouteEndpoint",
    "optimize",
]
