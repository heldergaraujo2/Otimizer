from dataclasses import dataclass, field


@dataclass(frozen=True)
class Delivery:
    """One eligible spreadsheet row. Never merge deliveries at this layer."""

    row_number: int
    source_id: str | None
    source_sequence: str | None
    source_stop: str | None
    tracking_number: str | None
    address: str | None
    neighborhood: str | None
    city: str | None
    zipcode: str | None
    latitude: float
    longitude: float


@dataclass
class PhysicalStop:
    """A real-world location containing one or more deliveries."""

    id: str
    latitude: float
    longitude: float
    deliveries: list[Delivery] = field(default_factory=list)

    @property
    def delivery_count(self) -> int:
        return len(self.deliveries)
