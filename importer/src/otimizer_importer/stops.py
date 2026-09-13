from collections import defaultdict
import math
import re
import unicodedata

from .models import Delivery, PhysicalStop

DEFAULT_ADDRESS_TOLERANCE_METERS = 50.0


def coordinate_key(latitude: float, longitude: float, precision: int = 6) -> tuple[float, float]:
    """Create a deterministic physical-location key.

    Exact/rounded coordinates remain the primary grouping mechanism. Address
    reconciliation is used only as a controlled fallback for GPS jitter.
    """
    return round(latitude, precision), round(longitude, precision)


def _normalize_address(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _distance_meters(first: Delivery, second: Delivery) -> float:
    """Return great-circle distance between two delivery coordinates."""
    earth_radius_m = 6_371_000.0
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(second.longitude - first.longitude)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def group_physical_stops(
    deliveries: list[Delivery],
    *,
    address_tolerance_meters: float = DEFAULT_ADDRESS_TOLERANCE_METERS,
) -> list[PhysicalStop]:
    """Group deliveries into physical stops without using source Stop/Sequence.

    Deliveries sharing the same coordinate are always grouped. Distinct
    coordinates are additionally grouped only when their normalized addresses
    match and their coordinates are within ``address_tolerance_meters``. This
    handles small GPS variations without merging nearby, unrelated addresses.
    """
    if address_tolerance_meters < 0:
        raise ValueError("address_tolerance_meters cannot be negative")

    grouped: dict[tuple[float, float], list[Delivery]] = defaultdict(list)
    for delivery in deliveries:
        grouped[coordinate_key(delivery.latitude, delivery.longitude)].append(delivery)

    stops: list[PhysicalStop] = []
    address_groups: dict[str, list[PhysicalStop]] = defaultdict(list)

    for index, ((latitude, longitude), members) in enumerate(grouped.items(), start=1):
        stop = PhysicalStop(
            id=f"stop-{index:04d}",
            latitude=latitude,
            longitude=longitude,
            deliveries=members,
        )
        address = _normalize_address(members[0].address)
        if address is None:
            stops.append(stop)
            continue

        matching_stop = next(
            (
                candidate
                for candidate in address_groups[address]
                if _distance_meters(members[0], candidate.deliveries[0]) <= address_tolerance_meters
            ),
            None,
        )
        if matching_stop is None:
            address_groups[address].append(stop)
            stops.append(stop)
        else:
            matching_stop.deliveries.extend(members)

    return stops
