from dataclasses import dataclass, replace

from .location import LocationDataProvider, LocationEvidence
from .metrics import RouteMetrics, calculate_route_metrics
from .models import Delivery, PhysicalStop, Route
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


def _validate_route_coverage(
    deliveries: tuple[Delivery, ...],
    physical_stops: tuple[PhysicalStop, ...],
    route: Route,
) -> None:
    """Enforce exact Delivery -> PhysicalStop -> Route coverage invariants."""
    expected_rows = {delivery.row_number for delivery in deliveries}
    routed_deliveries = [
        delivery
        for route_stop in route.stops
        for delivery in route_stop.physical_stop.deliveries
    ]
    routed_rows = [delivery.row_number for delivery in routed_deliveries]

    if len(routed_rows) != len(set(routed_rows)) or set(routed_rows) != expected_rows:
        raise ValueError("Optimized route does not contain every eligible delivery exactly once")

    expected_stop_ids = {stop.id for stop in physical_stops}
    routed_stop_ids = [route_stop.physical_stop.id for route_stop in route.stops]
    if len(routed_stop_ids) != len(set(routed_stop_ids)) or set(routed_stop_ids) != expected_stop_ids:
        raise ValueError("Optimized route does not contain every physical stop exactly once")

    if any(not route_stop.physical_stop.deliveries for route_stop in route.stops):
        raise ValueError("Optimized route contains a physical stop without deliveries")

    if tuple(stop.sequence for stop in route.stops) != tuple(range(1, len(route.stops) + 1)):
        raise ValueError("Optimized route sequence numbers are not contiguous")


def _location_cache_key(evidence: LocationEvidence) -> tuple[object, ...]:
    """Build a conservative key that never conflates different address evidence."""
    return (
        evidence.latitude,
        evidence.longitude,
        evidence.normalized_address,
        evidence.number,
        evidence.quadra,
        evidence.lote,
        evidence.zipcode,
        evidence.neighborhood,
        evidence.city,
    )


def _resolve_physical_stops(
    physical_stops: list[PhysicalStop],
    provider: LocationDataProvider | None,
) -> list[PhysicalStop]:
    """Resolve each delivery once per evidence key and retain the strongest result."""
    if provider is None:
        return physical_stops

    cache: dict[tuple[object, ...], object] = {}
    resolved: list[PhysicalStop] = []
    for stop in physical_stops:
        candidates = []
        for delivery in stop.deliveries:
            evidence = LocationEvidence.from_delivery(delivery)
            key = _location_cache_key(evidence)
            if key not in cache:
                cache[key] = provider.resolve(evidence)
            location = cache[key]
            if location is not None:
                candidates.append(location)
        if not candidates:
            resolved.append(stop)
            continue
        best = max(candidates, key=lambda location: location.confidence)
        resolved.append(
            replace(
                stop,
                latitude=best.latitude,
                longitude=best.longitude,
                location_confidence=best.confidence,
                location_source=best.source,
                property_latitude=best.property_latitude,
                property_longitude=best.property_longitude,
                access_latitude=best.access_latitude,
                access_longitude=best.access_longitude,
                cadastral_id=best.cadastral_id,
            )
        )
    return resolved


def _resolve_missing_coordinates(
    deliveries: list[Delivery],
    provider: LocationDataProvider | None,
) -> tuple[list[Delivery], tuple[int, ...]]:
    """Resolve deliveries that have no complete GPS pair before stop grouping."""
    if provider is None:
        return (
            [
                delivery
                for delivery in deliveries
                if delivery.latitude is not None and delivery.longitude is not None
            ],
            tuple(
                delivery.row_number
                for delivery in deliveries
                if delivery.latitude is None or delivery.longitude is None
            ),
        )

    resolved_deliveries: list[Delivery] = []
    unresolved_rows: list[int] = []

    for delivery in deliveries:
        if delivery.latitude is not None and delivery.longitude is not None:
            resolved_deliveries.append(delivery)
            continue

        evidence = LocationEvidence.from_delivery(delivery)
        location = provider.resolve(evidence)

        if location is None:
            unresolved_rows.append(delivery.row_number)
            continue

        resolved_deliveries.append(
            replace(
                delivery,
                latitude=location.latitude,
                longitude=location.longitude,
            )
        )

    return resolved_deliveries, tuple(unresolved_rows)


def optimize_deliveries_file(
    path: str,
    *,
    routing_provider: RoutingProvider | None = None,
    location_provider: LocationDataProvider | None = None,
    origin: RouteEndpoint | None = None,
    destination: RouteEndpoint | None = None,
    start_index: int = 0,
    return_to_start: bool = False,
    objective: OptimizationObjective = OptimizationObjective.TIME,
) -> OptimizationServiceResult:
    """Run the complete XLSX-to-route application workflow."""
    imported = import_result(path)

    deliveries, missing_location_rows = _resolve_missing_coordinates(
        list(imported.deliveries),
        location_provider,
    )
    if not deliveries:
        raise ValueError("Workbook contains no deliveries with resolvable location")

    physical_stops = group_physical_stops(deliveries)
    physical_stops = _resolve_physical_stops(physical_stops, location_provider)
    physical_stops_tuple = tuple(physical_stops)
    full_matrix = build_route_matrix(
        physical_stops,
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
    _validate_route_coverage(tuple(deliveries), physical_stops_tuple, result.route)
    route_metrics = calculate_route_metrics(
        result.route,
        physical_stops,
        problem.matrix,
        return_to_start=result.return_to_start,
        origin_id=result.origin.id if result.origin is not None else None,
        origin_metric=result.origin_metric,
        destination_id=result.destination.id if result.destination is not None else None,
        destination_metric=result.destination_metric,
    )
    unresolved_rows = tuple(
        sorted(set(imported.unresolved_rows) | set(missing_location_rows))
    )
    service_result = OptimizationServiceResult(
        eligible_delivery_count=len(deliveries),
        unresolved_rows=unresolved_rows,
        physical_stops=physical_stops_tuple,
        optimization=result,
        route_metrics=route_metrics,
    )
    if not service_result.coverage_complete:
        raise ValueError("Optimized route does not provide complete delivery and physical-stop coverage")
    return service_result
