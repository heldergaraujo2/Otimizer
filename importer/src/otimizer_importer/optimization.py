from dataclasses import dataclass
from functools import lru_cache

from .models import PhysicalStop, Route
from .optimizer import OptimizationError
from .routing import TravelMetric
from .types import OptimizationObjective, RouteEndpoint


@dataclass(frozen=True)
class OptimizationProblem:
    """Configuration for producing an optimized physical-stop route."""
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
    def from_full_matrix(cls, stops, full_matrix, *, origin=None, destination=None, start_index=0, return_to_start=False, objective=OptimizationObjective.TIME):
        size = len(stops)
        expected = size + (1 if origin is not None else 0) + (1 if destination is not None else 0)
        if len(full_matrix) != expected or any(len(row) != expected for row in full_matrix):
            raise ValueError("Full routing matrix size does not match endpoints and physical stops")
        origin_offset = 1 if origin is not None else 0
        stop_start = origin_offset
        stop_end = stop_start + size
        matrix = tuple(tuple(row[stop_start:stop_end]) for row in full_matrix[stop_start:stop_end])
        origin_metrics = tuple(full_matrix[0][stop_start:stop_end]) if origin is not None else None
        destination_index = expected - 1
        destination_metrics = tuple(row[destination_index] for row in full_matrix[stop_start:stop_end]) if destination is not None else None
        return cls(stops=stops, matrix=matrix, start_index=start_index, return_to_start=return_to_start, objective=objective, origin=origin, destination=destination, origin_metrics=origin_metrics, destination_metrics=destination_metrics)

    def __post_init__(self):
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


def _metric_cost(metric, objective):
    return (metric.distance_meters, metric.duration_seconds) if objective == OptimizationObjective.DISTANCE else (metric.duration_seconds, metric.distance_meters)


def _add_cost(left, right):
    return left[0] + right[0], left[1] + right[1]


def _order_cost(order, problem):
    total = (0.0, 0.0)
    if problem.origin_metrics is not None:
        metric = problem.origin_metrics[order[0]]
        if metric is None:
            return None
        total = _add_cost(total, _metric_cost(metric, problem.objective))
    for current, following in zip(order, order[1:]):
        metric = problem.matrix[current][following]
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


def _heuristic_starts(problem):
    if problem.origin_metrics is None:
        return (problem.start_index,)
    reachable = [index for index, metric in enumerate(problem.origin_metrics) if metric is not None]
    if not reachable:
        return tuple(range(len(problem.stops)))
    limit = min(12, len(reachable))
    ranked = sorted(reachable, key=lambda index: (*_metric_cost(problem.origin_metrics[index], problem.objective), index))
    selected = ranked[:limit]
    if len(reachable) > limit:
        step = max(1, len(ranked) // limit)
        selected = sorted(set(selected + ranked[::step]))[:limit]
    return tuple(selected)


def _greedy_order(stops, matrix, starts, objective, origin_metrics, destination_metrics, return_to_start):
    best = None
    for start in starts:
        remaining = set(range(len(stops)))
        remaining.remove(start)
        order = [start]
        total = (0.0, 0.0)
        current = start
        if origin_metrics is not None:
            metric = origin_metrics[start]
            if metric is None:
                continue
            total = _add_cost(total, _metric_cost(metric, objective))
        while remaining:
            candidates = [index for index in remaining if matrix[current][index] is not None]
            if not candidates:
                break
            next_index = min(candidates, key=lambda index: (*_metric_cost(matrix[current][index], objective), index))
            total = _add_cost(total, _metric_cost(matrix[current][next_index], objective))
            order.append(next_index)
            remaining.remove(next_index)
            current = next_index
        if remaining:
            continue
        if destination_metrics is not None:
            metric = destination_metrics[current]
            if metric is None:
                continue
            total = _add_cost(total, _metric_cost(metric, objective))
        elif return_to_start:
            metric = matrix[current][start]
            if metric is None:
                continue
            total = _add_cost(total, _metric_cost(metric, objective))
        candidate = (total, tuple(order))
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise OptimizationError("No complete road-network route satisfies the endpoint constraints")
    return best[1]


def _two_opt(order, problem):
    """Improve a complete route without changing required endpoints."""
    current = tuple(order)
    current_cost = _order_cost(current, problem)
    if current_cost is None:
        return current
    end_index = len(current) - 1 if problem.destination_metrics is None else len(current) - 2
    while True:
        best_order = current
        best_cost = current_cost
        for start in range(1, max(1, end_index)):
            for end in range(start + 1, end_index + 1):
                candidate = current[:start] + current[start:end + 1][::-1] + current[end + 1:]
                candidate_cost = _order_cost(candidate, problem)
                if candidate_cost is not None and candidate_cost < best_cost:
                    best_order, best_cost = candidate, candidate_cost
        if best_order == current:
            return current
        current, current_cost = best_order, best_cost


def _best_effort_order(problem):
    """Return every stop while minimizing unavailable legs before route cost."""
    size = len(problem.stops)
    if size == 0:
        return ()
    starts = _heuristic_starts(problem) or (problem.start_index,)
    if size <= 14:
        best = None
        for start in starts:
            remaining = tuple(index for index in range(size) if index != start)

            @lru_cache(maxsize=None)
            def solve(current, mask):
                if mask == 0:
                    missing = 0
                    cost = (0.0, 0.0)
                    if problem.destination_metrics is not None:
                        metric = problem.destination_metrics[current]
                        if metric is None:
                            missing = 1
                        else:
                            cost = _add_cost(cost, _metric_cost(metric, problem.objective))
                    elif problem.return_to_start:
                        metric = problem.matrix[current][start]
                        if metric is None:
                            missing = 1
                        else:
                            cost = _add_cost(cost, _metric_cost(metric, problem.objective))
                    return (missing, cost, ())
                best_suffix = None
                for offset, next_index in enumerate(remaining):
                    bit = 1 << offset
                    if not mask & bit:
                        continue
                    metric = problem.matrix[current][next_index]
                    edge_missing = int(metric is None)
                    edge_cost = (0.0, 0.0) if metric is None else _metric_cost(metric, problem.objective)
                    suffix = solve(next_index, mask ^ bit)
                    candidate = (edge_missing + suffix[0], _add_cost(edge_cost, suffix[1]), (next_index,) + suffix[2])
                    if best_suffix is None or candidate < best_suffix:
                        best_suffix = candidate
                return best_suffix

            suffix = solve(start, (1 << len(remaining)) - 1)
            missing, cost, path = suffix
            if problem.origin_metrics is not None:
                metric = problem.origin_metrics[start]
                if metric is None:
                    missing += 1
                else:
                    cost = _add_cost(_metric_cost(metric, problem.objective), cost)
            candidate = (missing, cost, (start,) + path)
            if best is None or candidate < best:
                best = candidate
        return best[2]

    # A bounded beam keeps the primary missing-leg objective visible several
    # steps ahead without the factorial cost of exact search. The beam is
    # deterministic and each expansion retains missing legs as the first key.
    beam_width = 64
    best = None
    for start in starts:
        initial_missing = 0
        initial_cost = (0.0, 0.0)
        if problem.origin_metrics is not None:
            metric = problem.origin_metrics[start]
            if metric is None:
                initial_missing = 1
            else:
                initial_cost = _add_cost(initial_cost, _metric_cost(metric, problem.objective))
        states = [(initial_missing, initial_cost, (start,), start)]
        remaining_all = frozenset(range(size))
        for _ in range(size - 1):
            expanded = []
            for missing, cost, order, current in states:
                remaining = remaining_all.difference(order)
                for next_index in remaining:
                    metric = problem.matrix[current][next_index]
                    edge_missing = int(metric is None)
                    edge_cost = (0.0, 0.0) if metric is None else _metric_cost(metric, problem.objective)
                    expanded.append((missing + edge_missing, _add_cost(cost, edge_cost), order + (next_index,), next_index))
            expanded.sort(key=lambda state: (state[0], state[1], state[2]))
            states = expanded[:beam_width]
        for missing, cost, order, current in states:
            endpoint_missing = 0
            endpoint_cost = (0.0, 0.0)
            if problem.destination_metrics is not None:
                metric = problem.destination_metrics[current]
                if metric is None:
                    endpoint_missing = 1
                else:
                    endpoint_cost = _metric_cost(metric, problem.objective)
            elif problem.return_to_start:
                metric = problem.matrix[current][start]
                if metric is None:
                    endpoint_missing = 1
                else:
                    endpoint_cost = _metric_cost(metric, problem.objective)
            candidate = (missing + endpoint_missing, _add_cost(cost, endpoint_cost), order)
            if best is None or candidate < best:
                best = candidate
    return best[2]


def _optimize_order(problem):
    size = len(problem.stops)
    if size == 0:
        return ()
    starts = _heuristic_starts(problem)
    try:
        if size <= 10:
            return _exact_order(problem.stops, problem.matrix, starts, problem.objective, problem.origin_metrics, problem.destination_metrics, problem.return_to_start)
        best = None
        for start in starts:
            seed = _greedy_order(problem.stops, problem.matrix, (start,), problem.objective, problem.origin_metrics, problem.destination_metrics, problem.return_to_start)
            improved = _two_opt(seed, problem)
            cost = _order_cost(improved, problem)
            if cost is not None and (best is None or (cost, improved) < best):
                best = (cost, improved)
        if best is None:
            raise OptimizationError("No complete road-network route satisfies the endpoint constraints")
        return best[1]
    except OptimizationError:
        return _best_effort_order(problem)


def optimize(problem: OptimizationProblem) -> OptimizationResult:
    order = _optimize_order(problem)
    ordered_stops = tuple(problem.stops[index] for index in order)
    origin_metric = problem.origin_metrics[order[0]] if problem.origin_metrics is not None else None
    destination_metric = problem.destination_metrics[order[-1]] if problem.destination_metrics is not None else None
    return OptimizationResult(
        route=Route.from_physical_stops(list(ordered_stops)),
        objective=problem.objective,
        start_index=None if problem.origin is not None else (problem.start_index if ordered_stops else None),
        return_to_start=problem.return_to_start,
        origin=problem.origin,
        destination=problem.destination,
        origin_metric=origin_metric,
        destination_metric=destination_metric,
    )