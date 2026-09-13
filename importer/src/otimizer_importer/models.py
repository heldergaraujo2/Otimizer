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
    quadra: str | None = None
    lote: str | None = None


@dataclass
class PhysicalStop:
    """A real-world location containing one or more deliveries."""

    id: str
    latitude: float
    longitude: float
    deliveries: list[Delivery] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("PhysicalStop.id cannot be empty")
        if not self.deliveries:
            raise ValueError("PhysicalStop must contain at least one delivery")

    @property
    def delivery_count(self) -> int:
        return len(self.deliveries)


@dataclass(frozen=True)
class OptimizedRouteStop:
    """A physical stop after the optimizer assigns its route position."""

    sequence: int
    physical_stop: PhysicalStop

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("Route sequence must start at 1")

    @property
    def id(self) -> str:
        return self.physical_stop.id

    @property
    def delivery_count(self) -> int:
        return self.physical_stop.delivery_count


@dataclass(frozen=True)
class Route:
    """An ordered, validated sequence of physical stops."""

    stops: tuple[OptimizedRouteStop, ...]

    @classmethod
    def from_physical_stops(cls, physical_stops: list[PhysicalStop]) -> "Route":
        if len({stop.id for stop in physical_stops}) != len(physical_stops):
            raise ValueError("Physical stop IDs must be unique")
        return cls(
            tuple(
                OptimizedRouteStop(sequence=index, physical_stop=stop)
                for index, stop in enumerate(physical_stops, start=1)
            )
        )

    def __post_init__(self) -> None:
        expected = tuple(range(1, len(self.stops) + 1))
        actual = tuple(stop.sequence for stop in self.stops)
        if actual != expected:
            raise ValueError("Route stop sequences must be contiguous and start at 1")
        ids = [stop.id for stop in self.stops]
        if len(set(ids)) != len(ids):
            raise ValueError("A physical stop cannot appear twice in a route")

    @property
    def physical_stop_count(self) -> int:
        return len(self.stops)

    @property
    def delivery_count(self) -> int:
        return sum(stop.delivery_count for stop in self.stops)


@dataclass(frozen=True)
class ImportResult:
    """Auditable outcome of an XLSX import."""

    deliveries: tuple[Delivery, ...]
    unresolved_rows: tuple[int, ...]
    data_rows_seen: int

    @property
    def eligible_delivery_count(self) -> int:
        return len(self.deliveries)

    @property
    def unresolved_count(self) -> int:
        return len(self.unresolved_rows)

    @property
    def accounted_rows(self) -> int:
        return self.eligible_delivery_count + self.unresolved_count

    def __post_init__(self) -> None:
        if self.data_rows_seen < 0:
            raise ValueError("data_rows_seen cannot be negative")
        if self.accounted_rows != self.data_rows_seen:
            raise ValueError("ImportResult must account for every data row")
        rows = [delivery.row_number for delivery in self.deliveries]
        if len(rows) != len(set(rows)):
            raise ValueError("A spreadsheet row cannot produce multiple deliveries")
        if len(self.unresolved_rows) != len(set(self.unresolved_rows)):
            raise ValueError("Unresolved spreadsheet rows must be unique")
        if set(rows) & set(self.unresolved_rows):
            raise ValueError("A spreadsheet row cannot be both eligible and unresolved")
