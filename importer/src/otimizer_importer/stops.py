from collections import defaultdict

from .models import Delivery, PhysicalStop


def coordinate_key(latitude: float, longitude: float, precision: int = 6) -> tuple[float, float]:
    """Create a deterministic physical-location key.

    This first version intentionally uses coordinates only. Address-aware
    reconciliation can be added later without changing the Delivery model.
    """
    return round(latitude, precision), round(longitude, precision)


def group_physical_stops(deliveries: list[Delivery]) -> list[PhysicalStop]:
    """Group deliveries by physical coordinate, ignoring source Stop/Sequence."""
    grouped: dict[tuple[float, float], list[Delivery]] = defaultdict(list)
    for delivery in deliveries:
        grouped[coordinate_key(delivery.latitude, delivery.longitude)].append(delivery)

    stops: list[PhysicalStop] = []
    for index, ((latitude, longitude), members) in enumerate(grouped.items(), start=1):
        stops.append(
            PhysicalStop(
                id=f"stop-{index:04d}",
                latitude=latitude,
                longitude=longitude,
                deliveries=members,
            )
        )
    return stops
