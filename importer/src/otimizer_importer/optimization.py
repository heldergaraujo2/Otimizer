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
class OptimizationProblem:
    """Configuration for producing a complete optimized physical-stop route."""

    stops: tuple[PhysicalStop, ...]
    matrix: tuple[tuple[TravelMetric | None, ...], ...]
    start_index: int = 0
    return_to_start: bool = False
    objective: OptimizationObjective = OptimizationObjective.TIME

    def __post_init__(self) -> None:
        if not self.stops:
            if self.matrix:
                raise ValueError("An empty stop set requires an empty routing matrix")
            return
        size = len(self.stops)
        if len(self.matrix) != size or any(len(row) != size for row in self.matrix):
            raise ValueError("Routing matrix size must match physical stops")
        if not 0 <= self.start_index < size:
            raise ValueError("start_index is outside the physical-stop list")
        if len({stop.id for stop in self.stops}) != size:
            raise ValueError("Physical stop IDs must be unique")


@dataclass(frozen=True)
class OptimizationResult:
    """Result containing the ordered route and the configuration used."""

    route: Route
    objective: OptimizationObjective
    start_index: int | None
    return_to_start: bool


def optimize(problem: OptimizationProblem) -> OptimizationResult:
    """Run the baseline optimizer with explicit, future-proof configuration."""
    route = optimize_nearest_neighbor(
        list(problem.stops),
        problem.matrix,
        start_index=problem.start_index,
        return_to_start=problem.return_to_start,
        objective=problem.objective,
    )
    return OptimizationResult(
        route=route,
        objective=problem.objective,
        start_index=problem.start_index if problem.stops else None,
        return_to_start=problem.return_to_start,
    )


__all__ = [
    "OptimizationError",
    "OptimizationObjective",
    "OptimizationProblem",
    "OptimizationResult",
    "optimize",
]
