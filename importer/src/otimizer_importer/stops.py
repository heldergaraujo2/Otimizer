from collections import defaultdict
import math
import re
import unicodedata

from .models import Delivery, PhysicalStop

DEFAULT_ADDRESS_TOLERANCE_METERS = 50.0


def coordinate_key(latitude: float, longitude: float, precision: int = 6) -> tuple[float, float]:
    """Create a deterministic physical-location key.

    Coordinates remain the primary spatial key. Address, Quadra and Lote are
    additional identity evidence used to reconcile small GPS variations and
    to prevent contradictory property information from being merged.
    """
    return round(latitude, precision), round(longitude, precision)


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _normalize_address(value: str | None) -> str | None:
    return _normalize_text(value)


def _location_evidence(delivery: Delivery) -> tuple[str | None, str | None, str | None]:
    return (
        _normalize_address(delivery.address),
        _normalize_text(delivery.quadra),
        _normalize_text(delivery.lote),
    )


def _compatible_location(first: Delivery, second: Delivery) -> bool:
    """Reject merges when known property/address fields contradict each other."""
    first_evidence = _location_evidence(first)
    second_evidence = _location_evidence(second)
    for left, right in zip(first_evidence, second_evidence):
        if left is not None and right is not None and left != right:
            return False
    return True


def _has_shared_strong_evidence(first: Delivery, second: Delivery) -> bool:
    """Return whether the pair shares an explicit location identity signal."""
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

    Exact coordinate groups are merged only when their known address/Quadra/
    Lote evidence is mutually compatible. Distinct coordinates can be merged
    for GPS jitter when they share strong location evidence and are within
    ``address_tolerance_meters``. Missing optional evidence never invalidates a
    delivery; contradictory known evidence prevents an unsafe merge.
    """
    if address_tolerance_meters < 0:
        raise ValueError("address_tolerance_meters cannot be negative")

    grouped: dict[tuple[float, float], list[Delivery]] = defaultdict(list)
    for delivery in deliveries:
        grouped[coordinate_key(delivery.latitude, delivery.longitude)].append(delivery)

    stops: list[PhysicalStop] = []
    address_groups: dict[tuple[str | None, str | None, str | None], list[PhysicalStop]] = defaultdict(list)

    for index, ((latitude, longitude), members) in enumerate(grouped.items(), start=1):
        # An identical GPS coordinate is not sufficient to merge contradictory
        # property identities (for example different lots at one geocoded point).
        compatible_members: list[Delivery] = []
        split_members: list[list[Delivery]] = []
        for member in members:
            target = next(
                (
                    existing
                    for existing in split_members
                    if all(_compatible_location(member, candidate) for candidate in existing)
                ),
                None,
            )
            if target is None:
                target = []
                split_members.append(target)
            target.append(member)

        for member_group in split_members:
            stop = PhysicalStop(
                id=f"stop-{len(stops) + 1:04d}",
                latitude=latitude,
                longitude=longitude,
                deliveries=member_group,
            )
            stops.append(stop)

            for delivery in member_group:
                evidence = _location_evidence(delivery)
                if _has_shared_strong_evidence(delivery, member_group[0]):
                    address_groups[evidence].append(stop)

    # Reconcile neighboring GPS points when the property identity agrees.
    reconciled: list[PhysicalStop] = []
    for stop in stops:
        representative = stop.deliveries[0]
        matching_stop = next(
            (
                candidate
                for candidate in reconciled
                if _distance_meters(representative, candidate.deliveries[0]) <= address_tolerance_meters
                and _has_shared_strong_evidence(representative, candidate.deliveries[0])
                and _compatible_location(representative, candidate.deliveries[0])
            ),
            None,
        )
        if matching_stop is None:
            reconciled.append(stop)
        else:
            matching_stop.deliveries.extend(stop.deliveries)

    return reconciled
