from dataclasses import dataclass

from .models import PhysicalStop, Route
from .optimization import OptimizationObjective, OptimizationResult, RouteEndpoint, OptimizationProblem, optimize
from .routing import RoutingProvider, build_route_matrix
from .stops import group_physical_stops
from .xlsx import import_result


@dataclass(frozen=True)
class OptimizationServiceResult:
    """Application-level result containing import, stops and optimized route."""

    eligible_delivery_count: int
    unresolved_rows: tuple[int, ...]
    physical_stops: tuple[PhysicalStop, ...]
    optimization: OptimizationResult

    @property
    def route(self) -> Route:
        return self.optimization.route

    @property
    def physical_stop_count(self) -> int:
        return len(self.physical_stops)

    @property
    def pending_count(self) -> int:
        return len(self.unresolved_rows)


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
    return OptimizationServiceResult(
        eligible_delivery_count=imported.eligible_delivery_count,
        unresolved_rows=imported.unresolved_rows,
        physical_stops=physical_stops,
        optimization=result,
    )
