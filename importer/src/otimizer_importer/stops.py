from collections import defaultdict
import math
import re
import unicodedata

from .models import Delivery, PhysicalStop

DEFAULT_ADDRESS_TOLERANCE_METERS = 50.0


def coordinate_key(latitude: float, longitude: float, precision: int = 6) -> tuple[float, float]:
    """Create a deterministic physical-location key.

    Coordinates are the spatial index, while address, house number, Quadra and
    Lote are independent identity evidence. Missing evidence does not block a
    merge; contradictory known evidence does.
    """
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
    """Return independent address identity evidence for one delivery."""
    return (
        delivery.normalized_address or _normalize_address(delivery.address),
        _normalize_number(delivery.number),
        _normalize_text(delivery.quadra),
        _normalize_text(delivery.lote),
    )


def _property_compatible(first: Delivery, second: Delivery) -> bool:
    """Reject a merge when any known identity field contradicts."""
    return all(
        left is None or right is None or left == right
        for left, right in zip(_location_evidence(first), _location_evidence(second))
    )


def _has_shared_strong_evidence(first: Delivery, second: Delivery) -> bool:
    """Require at least one explicit shared identity field for GPS-jitter merges."""
    first_evidence = _location_evidence(first)
    second_evidence = _location_evidence(second)
    return any(
        left is not None and left == right
        for left, right in zip(first_evidence, second_evidence)
    )


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

    The decision uses latitude/longitude together with every available identity
    field: normalized address, house number, Quadra and Lote. Missing fields are
    neutral. Explicit conflicts remain separate. Distinct coordinates can be
    reconciled for GPS jitter only when at least one explicit identity field
    agrees and all known fields remain compatible.
    """
    if address_tolerance_meters < 0:
        raise ValueError("address_tolerance_meters cannot be negative")

    grouped: dict[tuple[float, float], list[Delivery]] = defaultdict(list)
    for delivery in deliveries:
        # Deliveries without a complete GPS pair are preserved by the import
        # layer and handled by the geolocation stage before routing. They
        # cannot form a routable PhysicalStop at this stage.
        if delivery.latitude is None or delivery.longitude is None:
            continue
        grouped[coordinate_key(delivery.latitude, delivery.longitude)].append(delivery)

    stops: list[PhysicalStop] = []

    for latitude, longitude in grouped:
        members = grouped[(latitude, longitude)]
        split_members: list[list[Delivery]] = []
        for member in members:
            target = next(
                (
                    existing
                    for existing in split_members
                    if all(_property_compatible(member, candidate) for candidate in existing)
                ),
                None,
            )
            if target is None:
                target = []
                split_members.append(target)
            target.append(member)

        for member_group in split_members:
            stops.append(
                PhysicalStop(
                    id=f"stop-{len(stops) + 1:04d}",
                    latitude=latitude,
                    longitude=longitude,
                    deliveries=member_group,
                )
            )

    # Reconcile neighboring GPS points only when explicit location evidence
    # agrees. Proximity alone never merges two unrelated addresses. Check every
    # member already in the candidate stop to prevent transitive conflicts.
    reconciled: list[PhysicalStop] = []
    for stop in stops:
        representative = stop.deliveries[0]
        matching_stop = next(
            (
                candidate
                for candidate in reconciled
                if _distance_meters(representative, candidate.deliveries[0]) <= address_tolerance_meters
                and all(
                    _has_shared_strong_evidence(representative, existing)
                    and _property_compatible(representative, existing)
                    for existing in candidate.deliveries
                )
                and all(
                    _property_compatible(delivery, existing)
                    for delivery in stop.deliveries
                    for existing in candidate.deliveries
                )
            ),
            None,
        )
        if matching_stop is None:
            reconciled.append(stop)
        else:
            matching_stop.deliveries.extend(stop.deliveries)

    return reconciled
