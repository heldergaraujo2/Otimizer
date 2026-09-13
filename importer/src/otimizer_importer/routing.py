from dataclasses import dataclass
import json
import os
from typing import Protocol, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import PhysicalStop
from .types import RouteEndpoint


DEFAULT_OSRM_BASE_URL = "https://router.project-osrm.org"
DEFAULT_OSRM_TIMEOUT_SECONDS = 15.0
DEFAULT_OSRM_MAX_LOCATIONS = 100


@dataclass(frozen=True)
class TravelMetric:
    """Road-network travel metric between two locations."""

    distance_meters: float
    duration_seconds: float


class RoutingError(RuntimeError):
    """Raised when the routing provider cannot produce a road-network result."""


class RoutingProvider(Protocol):
    """Interface implemented by road-network routing providers."""

    def table(
        self, locations: Sequence[PhysicalStop | RouteEndpoint]
    ) -> tuple[tuple[TravelMetric | None, ...], ...]: ...


def _configured_osrm_base_url() -> str:
    return os.getenv("OTIMIZER_OSRM_BASE_URL", DEFAULT_OSRM_BASE_URL).strip() or DEFAULT_OSRM_BASE_URL


def _configured_osrm_timeout() -> float:
    raw = os.getenv("OTIMIZER_OSRM_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_OSRM_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_OSRM_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_OSRM_TIMEOUT_SECONDS


def _configured_osrm_max_locations() -> int:
    raw = os.getenv("OTIMIZER_OSRM_MAX_LOCATIONS")
    if raw is None:
        return DEFAULT_OSRM_MAX_LOCATIONS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_OSRM_MAX_LOCATIONS
    return max(2, value)


class OSRMRoutingProvider:
    """Routing provider backed by the OSRM Table API."""

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        base_url: str | None = None,
        max_locations: int | None = None,
    ) -> None:
        self.timeout_seconds = _configured_osrm_timeout() if timeout_seconds is None else timeout_seconds
        self.base_url = _configured_osrm_base_url() if base_url is None else base_url
        self.max_locations = _configured_osrm_max_locations() if max_locations is None else max(2, max_locations)

    def table(self, locations: Sequence[PhysicalStop | RouteEndpoint]) -> tuple[tuple[TravelMetric | None, ...], ...]:
        return fetch_osrm_table(
            list(locations),
            timeout_seconds=self.timeout_seconds,
            base_url=self.base_url,
            max_locations=self.max_locations,
        )


def _coordinates(locations: Sequence[PhysicalStop | RouteEndpoint]) -> str:
    return ";".join(f"{location.longitude},{location.latitude}" for location in locations)


def build_osrm_table_url(locations: list[PhysicalStop | RouteEndpoint], base_url: str = DEFAULT_OSRM_BASE_URL) -> str:
    """Build an OSRM Table request for physical stops and external endpoints."""
    if not locations:
        raise ValueError("At least one location is required")
    coordinates = _coordinates(locations)
    return f"{base_url.rstrip('/')}/table/v1/driving/{coordinates}?annotations=distance,duration"


def parse_osrm_table(payload: str | bytes, expected_size: int) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Parse an OSRM Table response into a square road-network matrix."""
    try:
        data = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RoutingError("Invalid routing-provider JSON response") from exc
    if data.get("code") != "Ok":
        raise RoutingError(f"Routing provider returned {data.get('code', 'unknown')}")
    distances = data.get("distances")
    durations = data.get("durations")
    if not isinstance(distances, list) or not isinstance(durations, list):
        raise RoutingError("Routing response is missing distance/duration matrices")
    if len(distances) != expected_size or len(durations) != expected_size:
        raise RoutingError("Routing matrix size does not match requested locations")
    matrix: list[tuple[TravelMetric | None, ...]] = []
    for distance_row, duration_row in zip(distances, durations):
        if not isinstance(distance_row, list) or not isinstance(duration_row, list):
            raise RoutingError("Routing matrix contains an invalid row")
        if len(distance_row) != expected_size or len(duration_row) != expected_size:
            raise RoutingError("Routing matrix row size does not match requested locations")
        values: list[TravelMetric | None] = []
        for distance, duration in zip(distance_row, duration_row):
            if distance is None or duration is None:
                values.append(None)
                continue
            if not isinstance(distance, (int, float)) or not isinstance(duration, (int, float)):
                raise RoutingError("Routing matrix contains a non-numeric metric")
            values.append(TravelMetric(float(distance), float(duration)))
        matrix.append(tuple(values))
    return tuple(matrix)


def fetch_osrm_table(
    locations: list[PhysicalStop | RouteEndpoint],
    timeout_seconds: float = DEFAULT_OSRM_TIMEOUT_SECONDS,
    base_url: str = DEFAULT_OSRM_BASE_URL,
    max_locations: int = DEFAULT_OSRM_MAX_LOCATIONS,
) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Fetch a road-network matrix from OSRM without hiding unreachable pairs."""
    if not locations:
        raise ValueError("At least one location is required")
    if len(locations) > max_locations:
        raise RoutingError(
            f"Routing request contains {len(locations)} locations; maximum is {max_locations}"
        )
    url = build_osrm_table_url(locations, base_url=base_url)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Otimizer/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
    except Exception as exc:
        raise RoutingError("Could not reach the routing provider") from exc
    return parse_osrm_table(payload, len(locations))


def build_route_matrix(
    stops: list[PhysicalStop],
    origin: RouteEndpoint | None = None,
    destination: RouteEndpoint | None = None,
    *,
    provider: RoutingProvider | None = None,
) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Build one matrix ordered as optional origin, stops, optional destination."""
    locations: list[PhysicalStop | RouteEndpoint] = []
    if origin is not None:
        locations.append(origin)
    locations.extend(stops)
    if destination is not None:
        locations.append(destination)
    if provider is None:
        provider = OSRMRoutingProvider()
    return provider.table(locations)
