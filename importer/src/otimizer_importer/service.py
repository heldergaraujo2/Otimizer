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
        return self.routed_delivery_count == self.eligible_delivery_count and self.routed_stop_count == self.physical_stop_count

    @property
    def routing_complete(self) -> bool:
        return self.route_metrics.routing_complete

    @property
    def fully_resolved(self) -> bool:
        return self.coverage_complete and self.pending_count == 0 and self.routing_complete


def _validate_route_coverage(deliveries: tuple[Delivery, ...], physical_stops: tuple[PhysicalStop, ...], route: Route) -> None:
    expected_rows = {delivery.row_number for delivery in deliveries}
    routed_deliveries = [delivery for route_stop in route.stops for delivery in route_stop.physical_stop.deliveries]
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
    return (evidence.latitude, evidence.longitude, evidence.normalized_address, evidence.number, evidence.quadra, evidence.lote, evidence.zipcode, evidence.neighborhood, evidence.city)


def _resolve_physical_stops(physical_stops: list[PhysicalStop], provider: LocationDataProvider | None) -> list[PhysicalStop]:
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
        resolved.append(replace(stop, latitude=best.latitude, longitude=best.longitude, location_confidence=best.confidence, location_source=best.source, property_latitude=best.property_latitude, property_longitude=best.property_longitude, access_latitude=best.access_latitude, access_longitude=best.access_longitude, cadastral_id=best.cadastral_id))
    return resolved


def _resolve_missing_coordinates(deliveries: list[Delivery], provider: LocationDataProvider | None) -> tuple[list[Delivery], tuple[int, ...]]:
    """Resolve what can be resolved but retain every original row when it cannot."""
    resolved_deliveries: list[Delivery] = []
    unresolved_rows: list[int] = []
    for delivery in deliveries:
        if delivery.latitude is not None and delivery.longitude is not None:
            resolved_deliveries.append(delivery)
            continue
        location = provider.resolve(LocationEvidence.from_delivery(delivery)) if provider is not None else None
        if location is None:
            resolved_deliveries.append(delivery)
            unresolved_rows.append(delivery.row_number)
        else:
            resolved_deliveries.append(replace(delivery, latitude=location.latitude, longitude=location.longitude))
    return resolved_deliveries, tuple(unresolved_rows)


def _build_route_matrix_with_pending(stops: list[PhysicalStop], *, origin: RouteEndpoint | None, destination: RouteEndpoint | None, provider: RoutingProvider | None) -> tuple[tuple[object | None, ...], ...]:
    """Route only located stops and expand unavailable pending stops as None edges."""
    routable_stops = [stop for stop in stops if not stop.is_pending_location]
    if routable_stops:
        base_matrix = build_route_matrix(routable_stops, origin=origin, destination=destination, provider=provider)
        base_keys: list[tuple[str, str]] = []
        if origin is not None:
            base_keys.append(("endpoint", "origin"))
        base_keys.extend(("stop", stop.id) for stop in routable_stops)
        if destination is not None:
            base_keys.append(("endpoint", "destination"))
    else:
        base_matrix = build_route_matrix([], origin=origin, destination=destination, provider=provider) if origin is not None or destination is not None else ()
        base_keys = []
        if origin is not None:
            base_keys.append(("endpoint", "origin"))
        if destination is not None:
            base_keys.append(("endpoint", "destination"))

    full_keys: list[tuple[str, str] | None] = []
    if origin is not None:
        full_keys.append(("endpoint", "origin"))
    full_keys.extend(None if stop.is_pending_location else ("stop", stop.id) for stop in stops)
    if destination is not None:
        full_keys.append(("endpoint", "destination"))
    base_index = {key: index for index, key in enumerate(base_keys)}
    full_matrix: list[tuple[object | None, ...]] = []
    for source_key in full_keys:
        row: list[object | None] = []
        for destination_key in full_keys:
            if source_key is None or destination_key is None:
                row.append(None)
            else:
                row.append(base_matrix[base_index[source_key]][base_index[destination_key]])
        full_matrix.append(tuple(row))
    return tuple(full_matrix)


def optimize_deliveries_file(path: str, *, routing_provider: RoutingProvider | None = None, location_provider: LocationDataProvider | None = None, origin: RouteEndpoint | None = None, destination: RouteEndpoint | None = None, start_index: int = 0, return_to_start: bool = False, objective: OptimizationObjective = OptimizationObjective.TIME) -> OptimizationServiceResult:
    imported = import_result(path)
    deliveries, missing_location_rows = _resolve_missing_coordinates(list(imported.deliveries), location_provider)
    unresolved_rows = tuple(sorted(set(imported.unresolved_rows) | set(missing_location_rows)))

    if not deliveries:
        empty_route = Route.from_physical_stops([])
        empty_result = OptimizationResult(route=empty_route, objective=objective, start_index=None, return_to_start=False, origin=None, destination=None)
        return OptimizationServiceResult(eligible_delivery_count=0, unresolved_rows=unresolved_rows, physical_stops=(), optimization=empty_result, route_metrics=RouteMetrics(0.0, 0.0, ()))

    physical_stops = _resolve_physical_stops(group_physical_stops(deliveries), location_provider)
    physical_stops_tuple = tuple(physical_stops)
    full_matrix = _build_route_matrix_with_pending(physical_stops, origin=origin, destination=destination, provider=routing_provider)
    problem = OptimizationProblem.from_full_matrix(physical_stops_tuple, full_matrix, origin=origin, destination=destination, start_index=start_index, return_to_start=return_to_start, objective=objective)
    result = optimize(problem)
    _validate_route_coverage(tuple(deliveries), physical_stops_tuple, result.route)
    route_metrics = calculate_route_metrics(result.route, physical_stops, problem.matrix, return_to_start=result.return_to_start, origin_id=result.origin.id if result.origin is not None else None, origin_metric=result.origin_metric, destination_id=result.destination.id if result.destination is not None else None, destination_metric=result.destination_metric)
    service_result = OptimizationServiceResult(eligible_delivery_count=len(deliveries), unresolved_rows=unresolved_rows, physical_stops=physical_stops_tuple, optimization=result, route_metrics=route_metrics)
    if not service_result.coverage_complete:
        raise ValueError("Optimized route does not provide complete delivery and physical-stop coverage")
    return service_result
