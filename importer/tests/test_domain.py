import pytest

from otimizer_importer.models import Delivery, PhysicalStop, Route


def delivery(row: int, lat: float, lon: float) -> Delivery:
    return Delivery(
        row_number=row,
        source_id=f"id-{row}",
        source_sequence=None,
        source_stop="-",
        tracking_number=f"TN-{row}",
        address=f"Rua {row}",
        neighborhood=None,
        city="Cidade",
        zipcode=None,
        latitude=lat,
        longitude=lon,
    )


def stop(stop_id: str, row: int, lat: float, lon: float) -> PhysicalStop:
    return PhysicalStop(
        id=stop_id,
        latitude=lat,
        longitude=lon,
        deliveries=[delivery(row, lat, lon)],
    )


def test_route_numbers_every_physical_stop_and_preserves_deliveries():
    physical_stops = [
        stop("stop-a", 2, -16.0, -49.0),
        stop("stop-b", 3, -16.1, -49.1),
    ]

    route = Route.from_physical_stops(physical_stops)

    assert [item.sequence for item in route.stops] == [1, 2]
    assert [item.id for item in route.stops] == ["stop-a", "stop-b"]
    assert route.physical_stop_count == 2
    assert route.delivery_count == 2


def test_route_rejects_duplicate_physical_stop_ids():
    first = stop("stop-a", 2, -16.0, -49.0)
    second = stop("stop-a", 3, -16.1, -49.1)

    with pytest.raises(ValueError, match="Physical stop IDs must be unique"):
        Route.from_physical_stops([first, second])


def test_physical_stop_cannot_be_empty():
    with pytest.raises(ValueError, match="at least one delivery"):
        PhysicalStop(id="stop-empty", latitude=-16.0, longitude=-49.0)


def test_route_rejects_duplicate_route_positions():
    first = stop("stop-a", 2, -16.0, -49.0)
    second = stop("stop-b", 3, -16.1, -49.1)

    from otimizer_importer.models import OptimizedRouteStop

    with pytest.raises(ValueError, match="contiguous"):
        Route((OptimizedRouteStop(1, first), OptimizedRouteStop(3, second)))
