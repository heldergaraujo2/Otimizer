from dataclasses import dataclass
import json
import os
from typing import Protocol, Sequence
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


def build_osrm_table_url(
    locations: list[PhysicalStop | RouteEndpoint],
    base_url: str = DEFAULT_OSRM_BASE_URL,
    *,
    sources: Sequence[int] | None = None,
    destinations: Sequence[int] | None = None,
) -> str:
    """Build an OSRM Table request, optionally selecting source/destination rows."""
    if not locations:
        raise ValueError("At least one location is required")
    coordinates = _coordinates(locations)
    query = ["annotations=distance,duration"]
    if sources is not None:
        query.append("sources=" + ";".join(str(index) for index in sources))
    if destinations is not None:
        query.append("destinations=" + ";".join(str(index) for index in destinations))
    return f"{base_url.rstrip('/')}/table/v1/driving/{coordinates}?{'&'.join(query)}"


def parse_osrm_table(
    payload: str | bytes,
    expected_size: int,
    expected_columns: int | None = None,
) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Parse an OSRM Table response into a road-network matrix."""
    columns = expected_size if expected_columns is None else expected_columns
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
        if len(distance_row) != columns or len(duration_row) != columns:
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


def _fetch_osrm_request(
    locations: list[PhysicalStop | RouteEndpoint],
    *,
    timeout_seconds: float,
    base_url: str,
    sources: Sequence[int] | None = None,
    destinations: Sequence[int] | None = None,
) -> tuple[tuple[TravelMetric | None, ...], ...]:
    url = build_osrm_table_url(
        locations,
        base_url=base_url,
        sources=sources,
        destinations=destinations,
    )
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Otimizer/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
    except Exception as exc:
        raise RoutingError("Could not reach the routing provider") from exc
    expected_rows = len(sources) if sources is not None else len(locations)
    expected_columns = len(destinations) if destinations is not None else len(locations)
    return parse_osrm_table(payload, expected_rows, expected_columns)


def _chunks(size: int, chunk_size: int) -> list[range]:
    return [range(start, min(start + chunk_size, size)) for start in range(0, size, chunk_size)]


def _fetch_osrm_tiled_table(
    locations: list[PhysicalStop | RouteEndpoint],
    *,
    timeout_seconds: float,
    base_url: str,
    max_locations: int,
) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Fill a full matrix using bounded OSRM source/destination tiles."""
    size = len(locations)
    matrix: list[list[TravelMetric | None]] = [[None] * size for _ in range(size)]
    chunks = _chunks(size, max_locations)

    for source_chunk in chunks:
        source_indices = list(source_chunk)
        for destination_chunk in chunks:
            destination_indices = list(destination_chunk)
            if source_chunk == destination_chunk:
                tile_locations = [locations[index] for index in source_indices]
                tile = _fetch_osrm_request(
                    tile_locations,
                    timeout_seconds=timeout_seconds,
                    base_url=base_url,
                )
            else:
                tile_locations = [locations[index] for index in source_indices] + [
                    locations[index] for index in destination_indices
                ]
                source_local = list(range(len(source_indices)))
                destination_local = list(range(len(source_indices), len(tile_locations)))
                tile = _fetch_osrm_request(
                    tile_locations,
                    timeout_seconds=timeout_seconds,
                    base_url=base_url,
                    sources=source_local,
                    destinations=destination_local,
                )

            for row_offset, source_index in enumerate(source_indices):
                for column_offset, destination_index in enumerate(destination_indices):
                    matrix[source_index][destination_index] = tile[row_offset][column_offset]

    return tuple(tuple(row) for row in matrix)


def fetch_osrm_table(
    locations: list[PhysicalStop | RouteEndpoint],
    timeout_seconds: float = DEFAULT_OSRM_TIMEOUT_SECONDS,
    base_url: str = DEFAULT_OSRM_BASE_URL,
    max_locations: int = DEFAULT_OSRM_MAX_LOCATIONS,
) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Fetch a complete road-network matrix, batching requests when necessary."""
    if not locations:
        raise ValueError("At least one location is required")
    max_locations = max(2, max_locations)
    if len(locations) <= max_locations:
        return _fetch_osrm_request(
            locations,
            timeout_seconds=timeout_seconds,
            base_url=base_url,
        )
    return _fetch_osrm_tiled_table(
        locations,
        timeout_seconds=timeout_seconds,
        base_url=base_url,
        max_locations=max_locations,
    )


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
