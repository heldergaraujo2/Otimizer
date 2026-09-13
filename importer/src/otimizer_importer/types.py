from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class RouteEndpoint:
    """A fixed geographic endpoint that is not itself a delivery stop."""

    latitude: float
    longitude: float
    id: str = "endpoint"


class OptimizationObjective(str, Enum):
    """Primary metric used when selecting a route."""

    TIME = "time"
    DISTANCE = "distance"


__all__ = ["OptimizationObjective", "RouteEndpoint"]
