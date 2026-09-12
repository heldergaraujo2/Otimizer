from otimizer_importer.models import Delivery
from otimizer_importer.stops import group_physical_stops


def delivery(row: int, lat: float, lon: float, source_stop: str) -> Delivery:
    return Delivery(
        row_number=row,
        source_id=f"id-{row}",
        source_sequence=None,
        source_stop=source_stop,
        tracking_number=f"TN-{row}",
        address=f"Rua {row}",
        neighborhood=None,
        city="Cidade",
        zipcode=None,
        latitude=lat,
        longitude=lon,
    )


def test_same_location_groups_deliveries_and_preserves_records():
    deliveries = [
        delivery(2, -16.6869, -49.2648, "1"),
        delivery(3, -16.6869, -49.2648, "1"),
    ]

    stops = group_physical_stops(deliveries)

    assert len(stops) == 1
    assert stops[0].delivery_count == 2
    assert [d.tracking_number for d in stops[0].deliveries] == ["TN-2", "TN-3"]


def test_source_stop_does_not_merge_distinct_coordinates():
    deliveries = [
        delivery(2, -16.6869, -49.2648, "7"),
        delivery(3, -16.6900, -49.2700, "7"),
    ]

    stops = group_physical_stops(deliveries)

    assert len(stops) == 2
    assert sum(stop.delivery_count for stop in stops) == 2


def test_missing_source_sequence_is_not_relevant_to_grouping():
    first = delivery(2, -16.6869, -49.2648, "-")
    second = delivery(3, -16.6869, -49.2648, "-")

    first = Delivery(**{**first.__dict__, "source_sequence": None})
    second = Delivery(**{**second.__dict__, "source_sequence": None})

    stops = group_physical_stops([first, second])

    assert len(stops) == 1
    assert stops[0].delivery_count == 2
