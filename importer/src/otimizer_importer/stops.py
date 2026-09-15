from collections import defaultdict
import math
import re
import unicodedata

from .models import Delivery, PhysicalStop

DEFAULT_ADDRESS_TOLERANCE_METERS = 50.0


def coordinate_key(latitude: float, longitude: float, precision: int = 6) -> tuple[float, float]:
    return round(latitude, precision), round(longitude, precision)


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized or None


def _normalize_address(value: str | None) -> str | None:
    return _normalize_text(value)


def _normalize_number(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    if normalized.isdigit():
        return str(int(normalized))
    return normalized.replace(" ", "")


def _location_evidence(delivery: Delivery) -> tuple[str | None, str | None, str | None, str | None]:
    return (
        delivery.normalized_address or _normalize_address(delivery.address),
        _normalize_number(delivery.number),
        _normalize_text(delivery.quadra),
        _normalize_text(delivery.lote),
    )


def _property_compatible(first: Delivery, second: Delivery) -> bool:
    return all(left is None or right is None or left == right for left, right in zip(_location_evidence(first), _location_evidence(second)))


def _has_shared_strong_evidence(first: Delivery, second: Delivery) -> bool:
    first_evidence = _location_evidence(first)
    second_evidence = _location_evidence(second)
    return any(left is not None and left == right for left, right in zip(first_evidence, second_evidence))


def _distance_meters(first: Delivery, second: Delivery) -> float:
    earth_radius_m = 6_371_000.0
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(second.longitude - first.longitude)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def _pending_key(delivery: Delivery) -> tuple[object, ...]:
    address, number, quadra, lote = _location_evidence(delivery)
    return (address, number, quadra, lote, _normalize_text(delivery.zipcode), _normalize_text(delivery.neighborhood), _normalize_text(delivery.city))


def group_physical_stops(deliveries: list[Delivery], *, address_tolerance_meters: float = DEFAULT_ADDRESS_TOLERANCE_METERS) -> list[PhysicalStop]:
    """Group deliveries while preserving pending-location deliveries as routable route stops."""
    if address_tolerance_meters < 0:
        raise ValueError("address_tolerance_meters cannot be negative")

    grouped: dict[tuple[float, float], list[Delivery]] = defaultdict(list)
    pending: list[Delivery] = []
    for delivery in deliveries:
        if delivery.latitude is None or delivery.longitude is None:
            pending.append(delivery)
        else:
            grouped[coordinate_key(delivery.latitude, delivery.longitude)].append(delivery)

    stops: list[PhysicalStop] = []
    for latitude, longitude in grouped:
        members = grouped[(latitude, longitude)]
        split_members: list[list[Delivery]] = []
        for member in members:
            target = next((existing for existing in split_members if all(_property_compatible(member, candidate) for candidate in existing)), None)
            if target is None:
                target = []
                split_members.append(target)
            target.append(member)
        for member_group in split_members:
            stops.append(PhysicalStop(id=f"stop-{len(stops) + 1:04d}", latitude=latitude, longitude=longitude, deliveries=member_group))

    reconciled: list[PhysicalStop] = []
    for stop in stops:
        representative = stop.deliveries[0]
        matching_stop = next(
            (
                candidate
                for candidate in reconciled
                if not candidate.is_pending_location
                and _distance_meters(representative, candidate.deliveries[0]) <= address_tolerance_meters
                and all(_has_shared_strong_evidence(representative, existing) and _property_compatible(representative, existing) for existing in candidate.deliveries)
                and all(_property_compatible(delivery, existing) for delivery in stop.deliveries for existing in candidate.deliveries)
            ),
            None,
        )
        if matching_stop is None:
            reconciled.append(stop)
        else:
            matching_stop.deliveries.extend(stop.deliveries)

    pending_groups: dict[tuple[object, ...], list[Delivery]] = {}
    for delivery in pending:
        key = _pending_key(delivery)
        if not any(key):
            key = ("row", delivery.row_number)
        pending_groups.setdefault(key, []).append(delivery)
    for member_group in pending_groups.values():
        stops.append(PhysicalStop(id=f"stop-{len(stops) + 1:04d}", latitude=None, longitude=None, deliveries=member_group))

    return reconciled + [stop for stop in stops if stop not in reconciled]
