from __future__ import annotations

from typing import Protocol

from .models import PhysicalStop
from .routing import RouteEndpoint, TravelMetric

Location = PhysicalStop | RouteEndpoint
RoutingMatrix = tuple[tuple[TravelMetric | None, ...], ...]


class RoutingProvider(Protocol):
    """Interface implemented by services that calculate road-network costs."""

    def table(self, locations: list[Location]) -> RoutingMatrix:
        """Return a square travel-cost matrix for the supplied locations."""
        ...


class OsrmRoutingProvider:
    """OSRM-backed implementation of the routing-provider interface."""

    def __init__(
        self,
        *,
        base_url: str = "https://router.project-osrm.org",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def table(self, locations: list[Location]) -> RoutingMatrix:
        from .routing import fetch_osrm_table

        return fetch_osrm_table(
            locations,
            timeout_seconds=self.timeout_seconds,
            base_url=self.base_url,
        )


__all__ = ["Location", "RoutingMatrix", "RoutingProvider", "OsrmRoutingProvider"]
