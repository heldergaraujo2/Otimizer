from dataclasses import dataclass
from functools import lru_cache

from .models import PhysicalStop, Route
from .optimizer import OptimizationError
from .routing import TravelMetric
from .types import OptimizationObjective, RouteEndpoint


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

    @classmethod
    def from_full_matrix(
        cls,
        stops: tuple[PhysicalStop, ...],
        full_matrix: tuple[tuple[TravelMetric | None, ...], ...],
        *,
        origin: RouteEndpoint | None = None,
        destination: RouteEndpoint | None = None,
        start_index: int = 0,
        return_to_start: bool = False,
        objective: OptimizationObjective = OptimizationObjective.TIME,
    ) -> "OptimizationProblem":
        """Create a problem from matrix order: origin, stops, destination."""
        size = len(stops)
        expected = size + (1 if origin is not None else 0) + (1 if destination is not None else 0)
        if len(full_matrix) != expected or any(len(row) != expected for row in full_matrix):
            raise ValueError("Full routing matrix size does not match endpoints and physical stops")

        origin_offset = 1 if origin is not None else 0
        stop_start = origin_offset
        stop_end = stop_start + size
        matrix = tuple(tuple(row[stop_start:stop_end]) for row in full_matrix[stop_start:stop_end])
        origin_metrics = None
        if origin is not None:
            origin_metrics = tuple(full_matrix[0][stop_start:stop_end])
        destination_metrics = None
        if destination is not None:
            destination_index = expected - 1
            destination_metrics = tuple(row[destination_index] for row in full_matrix[stop_start:stop_end])

        return cls(
            stops=stops,
            matrix=matrix,
            start_index=start_index,
            return_to_start=return_to_start,
            objective=objective,
            origin=origin,
            destination=destination,
            origin_metrics=origin_metrics,
            destination_metrics=destination_metrics,
        )

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
    """Result containing the ordered route and endpoint metrics."""

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


def _add_cost(left: tuple[float, float], right: tuple[float, float]) -> tuple[float, float]:
    return left[0] + right[0], left[1] + right[1]


def _subtract_cost(left: tuple[float, float], right: tuple[float, float]) -> tuple[float, float]:
    return left[0] - right[0], left[1] - right[1]


def _order_cost(order, problem: OptimizationProblem):
    """Return total lexicographic objective cost for a complete order."""
    total = (0.0, 0.0)
    if problem.origin_metrics is not None:
        metric = problem.origin_metrics[order[0]]
        if metric is None:
            return None
        total = _add_cost(total, _metric_cost(metric, problem.objective))

    for current, next_index in zip(order, order[1:]):
        metric = problem.matrix[current][next_index]
        if metric is None:
            return None
        total = _add_cost(total, _metric_cost(metric, problem.objective))

    if problem.destination_metrics is not None:
        metric = problem.destination_metrics[order[-1]]
        if metric is None:
            return None
        total = _add_cost(total, _metric_cost(metric, problem.objective))
    elif problem.return_to_start:
        metric = problem.matrix[order[-1]][order[0]]
        if metric is None:
            return None
        total = _add_cost(total, _metric_cost(metric, problem.objective))
    return total


def _two_opt(order, problem: OptimizationProblem):
    """Improve a complete route while preserving required endpoints."""
    current = tuple(order)
    current_cost = _order_cost(current, problem)
    if current_cost is None:
        return current

    improved = True
    while improved:
        improved = False
        best_order = current
        best_cost = current_cost
        size = len(current)
        forward_prefix = [(0.0, 0.0)] * size
        reverse_prefix = [(0.0, 0.0)] * size
        reverse_missing = [0] * size
        for index in range(size - 1):
            forward = problem.matrix[current[index]][current[index + 1]]
            reverse = problem.matrix[current[index + 1]][current[index]]
            forward_prefix[index + 1] = (
                _add_cost(forward_prefix[index], _metric_cost(forward, problem.objective))
                if forward is not None else forward_prefix[index]
            )
            reverse_prefix[index + 1] = (
                _add_cost(reverse_prefix[index], _metric_cost(reverse, problem.objective))
                if reverse is not None else reverse_prefix[index]
            )
            reverse_missing[index + 1] = reverse_missing[index] + (reverse is None)

        final_end = size - 2 if problem.destination_metrics is not None else size - 1
        for start in range(1, max(1, final_end)):
            for end in range(start + 1, final_end + 1):
                left_old = problem.matrix[current[start - 1]][current[start]]
                left_new = problem.matrix[current[start - 1]][current[end]]
                if left_old is None or left_new is None:
                    continue
                if reverse_missing[end] - reverse_missing[start] > 0:
                    continue

                old_boundary = _metric_cost(left_old, problem.objective)
                new_boundary = _metric_cost(left_new, problem.objective)
                old_internal = _subtract_cost(forward_prefix[end], forward_prefix[start])
                new_internal = _subtract_cost(reverse_prefix[end], reverse_prefix[start])
                delta = _add_cost(
                    _subtract_cost(new_boundary, old_boundary),
                    _subtract_cost(new_internal, old_internal),
                )

                if end < size - 1:
                    right_old = problem.matrix[current[end]][current[end + 1]]
                    right_new = problem.matrix[current[start]][current[end + 1]]
                    if right_old is None or right_new is None:
                        continue
                    delta = _add_cost(
                        delta,
                        _subtract_cost(
                            _metric_cost(right_new, problem.objective),
                            _metric_cost(right_old, problem.objective),
                        ),
                    )
                elif problem.return_to_start:
                    return_old = problem.matrix[current[end]][current[0]]
                    return_new = problem.matrix[current[start]][current[0]]
                    if return_old is None or return_new is None:
                        continue
                    delta = _add_cost(
                        delta,
                        _subtract_cost(
                            _metric_cost(return_new, problem.objective),
                            _metric_cost(return_old, problem.objective),
                        ),
                    )

                candidate_cost = _add_cost(current_cost, delta)
                if candidate_cost < best_cost:
                    best_order = current[:start] + current[start:end + 1][::-1] + current[end + 1:]
                    best_cost = candidate_cost

        if best_order != current:
            current = best_order
            current_cost = best_cost
            improved = True

    return current


def _exact_order(stops, matrix, starts, objective, origin_metrics, destination_metrics, return_to_start):
    size = len(stops)
    best = None
    for start in starts:
        remaining = tuple(index for index in range(size) if index != start)

        @lru_cache(maxsize=None)
        def solve(current, mask):
            if mask == 0:
                if destination_metrics is not None:
                    metric = destination_metrics[current]
                    return None if metric is None else (_metric_cost(metric, objective), ())
                if return_to_start:
                    metric = matrix[current][start]
                    return None if metric is None else (_metric_cost(metric, objective), ())
                return ((0.0, 0.0), ())
            best_suffix = None
            for offset, next_index in enumerate(remaining):
                bit = 1 << offset
                if not mask & bit:
                    continue
                metric = matrix[current][next_index]
                if metric is None:
                    continue
                suffix = solve(next_index, mask ^ bit)
                if suffix is None:
                    continue
                candidate = (_add_cost(_metric_cost(metric, objective), suffix[0]), (next_index,) + suffix[1])
                if best_suffix is None or candidate < best_suffix:
                    best_suffix = candidate
            return best_suffix

        suffix = solve(start, (1 << len(remaining)) - 1)
        if suffix is None:
            continue
        total = suffix[0]
        if origin_metrics is not None:
            metric = origin_metrics[start]
            if metric is None:
                continue
            total = _add_cost(_metric_cost(metric, objective), total)
        candidate = (total, (start,) + suffix[1])
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise OptimizationError("No complete road-network route satisfies the endpoint constraints")
    return best[1]


def _greedy_order(stops, matrix, starts, objective, origin_metrics, destination_metrics, return_to_start):
    best = None
    for start in starts:
        remaining = set(range(len(stops)))
        remaining.remove(start)
        order = [start]
        current = start
        total = (0.0, 0.0)
        if origin_metrics is not None:
            metric = origin_metrics[start]
            if metric is None:
                continue
            total = _add_cost(total, _metric_cost(metric, objective))
        while remaining:
            candidates = [i for i in remaining if matrix[current][i] is not None]
            if not candidates:
                break
            next_index = min(candidates, key=lambda i: (*_metric_cost(matrix[current][i], objective), i))
            total = _add_cost(total, _metric_cost(matrix[current][next_index], objective))
            order.append(next_index)
            remaining.remove(next_index)
            current = next_index
        if remaining:
            continue
        if destination_metrics is not None:
            final = destination_metrics[current]
            if final is None:
                continue
            total = _add_cost(total, _metric_cost(final, objective))
        elif return_to_start:
            final = matrix[current][start]
            if final is None:
                continue
            total = _add_cost(total, _metric_cost(final, objective))
        candidate = (total, tuple(order))
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise OptimizationError("No complete road-network route satisfies the endpoint constraints")
    return best[1]


def _heuristic_starts(problem: OptimizationProblem) -> tuple[int, ...]:
    """Choose bounded deterministic starts for large routes with a free origin."""
    if problem.origin_metrics is None:
        return (problem.start_index,)

    reachable = [
        index for index, metric in enumerate(problem.origin_metrics)
        if metric is not None
    ]
    if not reachable:
        return ()

    limit = min(12, len(reachable))
    ranked = sorted(
        reachable,
        key=lambda index: (*_metric_cost(problem.origin_metrics[index], problem.objective), index),
    )
    selected = ranked[:limit]
    if len(reachable) > limit:
        step = max(1, len(ranked) // limit)
        selected.extend(ranked[::step][:limit])
    return tuple(dict.fromkeys(selected))


def _optimize_order(problem, starts):
    if len(problem.stops) <= 12:
        return _exact_order(problem.stops, problem.matrix, starts, problem.objective, problem.origin_metrics, problem.destination_metrics, problem.return_to_start)

    best = None
    for start in starts:
        greedy = _greedy_order(
            problem.stops,
            problem.matrix,
            (start,),
            problem.objective,
            problem.origin_metrics,
            problem.destination_metrics,
            problem.return_to_start,
        )
        improved = _two_opt(greedy, problem)
        cost = _order_cost(improved, problem)
        if cost is None:
            continue
        candidate = (cost, tuple(improved))
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise OptimizationError("No complete road-network route satisfies the endpoint constraints")
    return best[1]


def optimize(problem: OptimizationProblem) -> OptimizationResult:
    """Optimize the complete road trip while preserving every physical stop."""
    if not problem.stops:
        return OptimizationResult(Route.from_physical_stops([]), problem.objective, None, False, problem.origin, problem.destination)
    starts = _heuristic_starts(problem) if problem.origin is not None else (problem.start_index,)
    if not starts:
        raise OptimizationError("No road-network path reaches a physical stop from the origin")
    order = _optimize_order(problem, starts)
    route = Route.from_physical_stops([problem.stops[index] for index in order])
    origin_metric = problem.origin_metrics[order[0]] if problem.origin is not None else None
    destination_metric = problem.destination_metrics[order[-1]] if problem.destination is not None else None
    if problem.destination is not None and destination_metric is None:
        raise OptimizationError("Route cannot reach the destination from its final physical stop")
    return OptimizationResult(
        route, problem.objective,
        order[0] if problem.origin is None else None,
        problem.return_to_start if problem.origin is None else False,
        problem.origin, problem.destination, origin_metric, destination_metric,
    )


__all__ = ["OptimizationError", "OptimizationObjective", "OptimizationProblem", "OptimizationResult", "RouteEndpoint", "optimize"]
