from dataclasses import dataclass
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import PhysicalStop


@dataclass(frozen=True)
class TravelMetric:
    """Road-network travel metric between two physical stops."""

    distance_meters: float
    duration_seconds: float


class RoutingError(RuntimeError):
    """Raised when the routing provider cannot produce a road-network result."""


def build_osrm_table_url(stops: list[PhysicalStop], base_url: str = "https://router.project-osrm.org") -> str:
    """Build an OSRM Table request for supplied physical stops."""
    if not stops:
        raise ValueError("At least one physical stop is required")
    coordinates = ";".join(f"{stop.longitude},{stop.latitude}" for stop in stops)
    encoded = quote(coordinates, safe=",;.-")
    return f"{base_url.rstrip('/')}/table/v1/driving/{encoded}?annotations=distance%2Cduration"


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
        raise RoutingError("Routing matrix size does not match physical stops")

    matrix: list[tuple[TravelMetric | None, ...]] = []
    for distance_row, duration_row in zip(distances, durations):
        if not isinstance(distance_row, list) or not isinstance(duration_row, list):
            raise RoutingError("Routing matrix contains an invalid row")
        if len(distance_row) != expected_size or len(duration_row) != expected_size:
            raise RoutingError("Routing matrix row size does not match physical stops")
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


def fetch_osrm_table(stops: list[PhysicalStop], timeout_seconds: float = 15.0, base_url: str = "https://router.project-osrm.org") -> tuple[tuple[TravelMetric | None, ...], ...]:
    """Fetch a road-network matrix from OSRM without hiding unreachable pairs."""
    url = build_osrm_table_url(stops, base_url=base_url)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Otimizer/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
    except Exception as exc:
        raise RoutingError("Could not reach the routing provider") from exc
    return parse_osrm_table(payload, len(stops))
