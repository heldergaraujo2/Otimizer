from dataclasses import dataclass

from .metrics import RouteMetrics, calculate_route_metrics
from .models import PhysicalStop, Route
from .optimization import OptimizationObjective, OptimizationResult, RouteEndpoint, OptimizationProblem, optimize
from .routing import RoutingProvider, build_route_matrix
from .stops import group_physical_stops
from .xlsx import import_result


@dataclass(frozen=True)
class OptimizationServiceResult:
    """Application-level result ready for an API or frontend consumer."""

    eligible_delivery_count: int
    unresolved_rows: tuple[int, ...]
    physical_stops: tuple[PhysicalStop, ...]
    optimization: OptimizationResult
    route_metrics: RouteMetrics

    @property
    def route(self) -> Route:
        return self.optimization.route

    @property
    def physical_stop_count(self) -> int:
        return len(self.physical_stops)

    @property
    def routed_stop_count(self) -> int:
        return self.route.physical_stop_count

    @property
    def pending_count(self) -> int:
        return len(self.unresolved_rows)

    @property
    def routed_delivery_count(self) -> int:
        return self.route.delivery_count

    @property
    def coverage_complete(self) -> bool:
        """Whether every eligible delivery and physical stop is routed."""
        return (
            self.routed_delivery_count == self.eligible_delivery_count
            and self.routed_stop_count == self.physical_stop_count
        )

    @property
    def fully_resolved(self) -> bool:
        """Whether coverage is complete and there are no unresolved rows."""
        return self.coverage_complete and self.pending_count == 0


def optimize_deliveries_file(
    path: str,
    *,
    routing_provider: RoutingProvider | None = None,
    origin: RouteEndpoint | None = None,
    destination: RouteEndpoint | None = None,
    start_index: int = 0,
    return_to_start: bool = False,
    objective: OptimizationObjective = OptimizationObjective.TIME,
) -> OptimizationServiceResult:
    """Run the complete XLSX-to-route application workflow."""
    imported = import_result(path)
    physical_stops = tuple(group_physical_stops(list(imported.deliveries)))
    full_matrix = build_route_matrix(
        list(physical_stops),
        origin=origin,
        destination=destination,
        provider=routing_provider,
    )
    problem = OptimizationProblem.from_full_matrix(
        physical_stops,
        full_matrix,
        origin=origin,
        destination=destination,
        start_index=start_index,
        return_to_start=return_to_start,
        objective=objective,
    )
    result = optimize(problem)
    route_metrics = calculate_route_metrics(
        result.route,
        list(physical_stops),
        problem.matrix,
        return_to_start=result.return_to_start,
        origin_id=result.origin.id if result.origin is not None else None,
        origin_metric=result.origin_metric,
        destination_id=result.destination.id if result.destination is not None else None,
        destination_metric=result.destination_metric,
    )
    service_result = OptimizationServiceResult(
        eligible_delivery_count=imported.eligible_delivery_count,
        unresolved_rows=imported.unresolved_rows,
        physical_stops=physical_stops,
        optimization=result,
        route_metrics=route_metrics,
    )
    if not service_result.coverage_complete:
        raise ValueError("Optimized route does not provide complete delivery and physical-stop coverage")
    return service_result
