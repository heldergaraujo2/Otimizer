from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import math
import os
from typing import Protocol, Sequence
from urllib.request import Request, urlopen

from .models import PhysicalStop
from .types import RouteEndpoint


DEFAULT_OSRM_BASE_URL = "https://router.project-osrm.org"
DEFAULT_OSRM_TIMEOUT_SECONDS = 15.0
DEFAULT_OSRM_MAX_LOCATIONS = 100
DEFAULT_OSRM_MAX_CONCURRENT_REQUESTS = 4


@dataclass(frozen=True)
class TravelMetric:
    """Road-network travel metric between two locations."""
    distance_meters: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.distance_meters) or self.distance_meters < 0:
            raise ValueError("distance_meters must be a finite non-negative number")
        if not math.isfinite(self.duration_seconds) or self.duration_seconds < 0:
            raise ValueError("duration_seconds must be a finite non-negative number")


class RoutingError(RuntimeError):
    """Raised when the routing provider cannot produce a road-network result."""


class RoutingProvider(Protocol):
    def table(self, locations: Sequence[PhysicalStop | RouteEndpoint]) -> tuple[tuple[TravelMetric | None, ...], ...]: ...


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


def _configured_osrm_max_concurrent_requests() -> int:
    raw = os.getenv("OTIMIZER_OSRM_MAX_CONCURRENT_REQUESTS")
    if raw is None:
        return DEFAULT_OSRM_MAX_CONCURRENT_REQUESTS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_OSRM_MAX_CONCURRENT_REQUESTS
    return max(1, value)


class OSRMRoutingProvider:
    """Routing provider backed by the OSRM Table API."""
    def __init__(self, *, timeout_seconds: float | None = None, base_url: str | None = None, max_locations: int | None = None, max_concurrent_requests: int | None = None):
        self.timeout_seconds = _configured_osrm_timeout() if timeout_seconds is None else timeout_seconds
        self.base_url = _configured_osrm_base_url() if base_url is None else base_url
        self.max_locations = _configured_osrm_max_locations() if max_locations is None else max(2, max_locations)
        self.max_concurrent_requests = _configured_osrm_max_concurrent_requests() if max_concurrent_requests is None else max(1, max_concurrent_requests)

    def table(self, locations: Sequence[PhysicalStop | RouteEndpoint]) -> tuple[tuple[TravelMetric | None, ...], ...]:
        return fetch_osrm_table(list(locations), timeout_seconds=self.timeout_seconds, base_url=self.base_url, max_locations=self.max_locations, max_concurrent_requests=self.max_concurrent_requests)


def _coordinates(locations: Sequence[PhysicalStop | RouteEndpoint]) -> str:
    return ";".join(f"{location.longitude},{location.latitude}" for location in locations)


def build_osrm_table_url(locations: list[PhysicalStop | RouteEndpoint], base_url: str = DEFAULT_OSRM_BASE_URL, *, sources: Sequence[int] | None = None, destinations: Sequence[int] | None = None) -> str:
    if not locations:
        raise ValueError("At least one location is required")
    coordinates = _coordinates(locations)
    query = ["annotations=distance,duration"]
    if sources is not None:
        query.append("sources=" + ";".join(str(index) for index in sources))
    if destinations is not None:
        query.append("destinations=" + ";".join(str(index) for index in destinations))
    return f"{base_url.rstrip('/')}/table/v1/driving/{coordinates}?{'&'.join(query)}"


def parse_osrm_table(payload: str | bytes, expected_size: int, expected_columns: int | None = None) -> tuple[tuple[TravelMetric | None, ...], ...]:
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
            try:
                values.append(TravelMetric(float(distance), float(duration)))
            except ValueError as exc:
                raise RoutingError("Routing matrix contains an invalid metric") from exc
        matrix.append(tuple(values))
    return tuple(matrix)


def _fetch_osrm_request(locations: list[PhysicalStop | RouteEndpoint], *, timeout_seconds: float, base_url: str, sources: Sequence[int] | None = None, destinations: Sequence[int] | None = None) -> tuple[tuple[TravelMetric | None, ...], ...]:
    url = build_osrm_table_url(locations, base_url=base_url, sources=sources, destinations=destinations)
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


def _fetch_osrm_tiled_table(locations: list[PhysicalStop | RouteEndpoint], *, timeout_seconds: float, base_url: str, max_locations: int, max_concurrent_requests: int) -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Fill a full matrix with bounded, concurrently fetched OSRM tiles."""
    size = len(locations)
    matrix: list[list[TravelMetric | None]] = [[None] * size for _ in range(size)]
    chunk_size = max(1, (max_locations + 1) // 2)
    chunks = _chunks(size, chunk_size)

    def fetch_tile(source_chunk: range, destination_chunk: range):
        source_indices = list(source_chunk)
        destination_indices = list(destination_chunk)
        if source_chunk == destination_chunk:
            tile_locations = [locations[index] for index in source_indices]
            tile = _fetch_osrm_request(tile_locations, timeout_seconds=timeout_seconds, base_url=base_url)
            return source_indices, destination_indices, tile

        remaining_destinations = destination_indices
        while remaining_destinations:
            capacity = max_locations - len(source_indices)
            if capacity <= 0:
                raise RoutingError("OSRM tile cannot fit source locations within provider limit")
            destination_part = remaining_destinations[:capacity]
            remaining_destinations = remaining_destinations[capacity:]
            tile_locations = [locations[index] for index in source_indices] + [locations[index] for index in destination_part]
            source_local = list(range(len(source_indices)))
            destination_local = list(range(len(source_indices), len(tile_locations)))
            tile = _fetch_osrm_request(tile_locations, timeout_seconds=timeout_seconds, base_url=base_url, sources=source_local, destinations=destination_local)
            for row_offset, source_index in enumerate(source_indices):
                for column_offset, destination_index in enumerate(destination_part):
                    matrix[source_index][destination_index] = tile[row_offset][column_offset]
        return source_indices, destination_indices, None

    futures = {}
    with ThreadPoolExecutor(max_workers=max_concurrent_requests) as executor:
        for source_chunk in chunks:
            for destination_chunk in chunks:
                futures[executor.submit(fetch_tile, source_chunk, destination_chunk)] = (source_chunk, destination_chunk)

        for future in as_completed(futures):
            source_chunk, destination_chunk = futures[future]
            try:
                source_indices, destination_indices, tile = future.result()
            except Exception as exc:
                source_label = f"{source_chunk.start}:{source_chunk.stop}"
                destination_label = f"{destination_chunk.start}:{destination_chunk.stop}"
                raise RoutingError(
                    f"OSRM tile failed (sources {source_label}, destinations {destination_label})"
                ) from exc
            if tile is not None:
                for row_offset, source_index in enumerate(source_indices):
                    for column_offset, destination_index in enumerate(destination_indices):
                        matrix[source_index][destination_index] = tile[row_offset][column_offset]
    return tuple(tuple(row) for row in matrix)


def fetch_osrm_table(locations: list[PhysicalStop | RouteEndpoint], timeout_seconds: float = DEFAULT_OSRM_TIMEOUT_SECONDS, base_url: str = DEFAULT_OSRM_BASE_URL, max_locations: int = DEFAULT_OSRM_MAX_LOCATIONS, max_concurrent_requests: int = DEFAULT_OSRM_MAX_CONCURRENT_REQUESTS) -> tuple[tuple[TravelMetric | None, ...], ...]:
    if not locations:
        raise ValueError("At least one location is required")
    max_locations = max(2, max_locations)
    max_concurrent_requests = max(1, max_concurrent_requests)
    if len(locations) <= max_locations:
        return _fetch_osrm_request(locations, timeout_seconds=timeout_seconds, base_url=base_url)
    return _fetch_osrm_tiled_table(locations, timeout_seconds=timeout_seconds, base_url=base_url, max_locations=max_locations, max_concurrent_requests=max_concurrent_requests)


def _location_key(location: PhysicalStop | RouteEndpoint) -> tuple[float, float]:
    return (float(location.latitude), float(location.longitude))


def _deduplicate_locations(locations: Sequence[PhysicalStop | RouteEndpoint]) -> tuple[list[PhysicalStop | RouteEndpoint], list[int]]:
    unique: list[PhysicalStop | RouteEndpoint] = []
    index_by_key: dict[tuple[float, float], int] = {}
    expanded: list[int] = []
    for location in locations:
        key = _location_key(location)
        unique_index = index_by_key.get(key)
        if unique_index is None:
            unique_index = len(unique)
            index_by_key[key] = unique_index
            unique.append(location)
        expanded.append(unique_index)
    return unique, expanded


def _expand_matrix(matrix: tuple[tuple[TravelMetric | None, ...], ...], expanded_indices: Sequence[int]) -> tuple[tuple[TravelMetric | None, ...], ...]:
    return tuple(tuple(matrix[source_index][destination_index] for destination_index in expanded_indices) for source_index in expanded_indices)


def build_route_matrix(stops: list[PhysicalStop], origin: RouteEndpoint | None = None, destination: RouteEndpoint | None = None, *, provider: RoutingProvider | None = None) -> tuple[tuple[TravelMetric | None, ...], ...]:
    locations: list[PhysicalStop | RouteEndpoint] = []
    if origin is not None:
        locations.append(origin)
    locations.extend(stops)
    if destination is not None:
        locations.append(destination)
    if not locations:
        raise ValueError("At least one route location is required")
    if provider is None:
        provider = OSRMRoutingProvider()
    unique_locations, expanded_indices = _deduplicate_locations(locations)
    unique_matrix = provider.table(unique_locations)
    expected_size = len(unique_locations)
    if len(unique_matrix) != expected_size or any(len(row) != expected_size for row in unique_matrix):
        raise RoutingError("Routing provider returned a matrix with an invalid size")
    return _expand_matrix(unique_matrix, expanded_indices)
