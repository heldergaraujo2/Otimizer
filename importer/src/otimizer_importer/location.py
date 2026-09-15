from dataclasses import dataclass
from typing import Protocol

from .models import Delivery


@dataclass(frozen=True)
class LocationEvidence:
    """All source evidence available for resolving one delivery location."""

    latitude: float | None
    longitude: float | None
    address: str | None
    normalized_address: str | None
    number: str | None
    quadra: str | None
    lote: str | None
    zipcode: str | None
    neighborhood: str | None
    city: str | None

    @classmethod
    def from_delivery(cls, delivery: Delivery) -> "LocationEvidence":
        return cls(
            latitude=delivery.latitude,
            longitude=delivery.longitude,
            address=delivery.address,
            normalized_address=delivery.normalized_address,
            number=delivery.number,
            quadra=delivery.quadra,
            lote=delivery.lote,
            zipcode=delivery.zipcode,
            neighborhood=delivery.neighborhood,
            city=delivery.city,
        )


@dataclass(frozen=True)
class ResolvedLocation:
    """Resolved property/access location with an explicit confidence score."""

    latitude: float
    longitude: float
    confidence: float
    source: str
    property_latitude: float | None = None
    property_longitude: float | None = None
    access_latitude: float | None = None
    access_longitude: float | None = None
    cadastral_id: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Location confidence must be between 0 and 1")
        if not self.source:
            raise ValueError("Location source cannot be empty")


class LocationDataProvider(Protocol):
    """City/state-specific cadastral or geospatial data source."""

    def resolve(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        """Resolve the best known property/access point for the evidence."""


def gps_fallback(evidence: LocationEvidence) -> ResolvedLocation:
    """Return the original spreadsheet coordinate as the safe final fallback."""
    if evidence.latitude is None or evidence.longitude is None:
        raise ValueError("Cannot use GPS fallback without valid coordinates")
    return ResolvedLocation(
        latitude=evidence.latitude,
        longitude=evidence.longitude,
        confidence=0.25,
        source="xlsx-gps",
        property_latitude=evidence.latitude,
        property_longitude=evidence.longitude,
    )
