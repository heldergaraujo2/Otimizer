from otimizer_importer.models import Delivery
from otimizer_importer.stops import group_physical_stops


def delivery(
    row: int,
    lat: float,
    lon: float,
    source_stop: str,
    address: str | None = None,
) -> Delivery:
    return Delivery(
        row_number=row,
        source_id=f"id-{row}",
        source_sequence=None,
        source_stop=source_stop,
        tracking_number=f"TN-{row}",
        address=address if address is not None else f"Rua {row}",
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

    stops = group_physical_stops([first, second])

    assert len(stops) == 1
    assert stops[0].delivery_count == 2


def test_same_address_with_small_gps_jitter_groups_deliveries():
    deliveries = [
        delivery(2, -16.686900, -49.264800, "1", "Rua das Flores, 100"),
        delivery(3, -16.686940, -49.264820, "2", " RUA DAS FLORES 100 "),
    ]

    stops = group_physical_stops(deliveries)

    assert len(stops) == 1
    assert stops[0].delivery_count == 2


def test_same_address_beyond_tolerance_stays_separate():
    deliveries = [
        delivery(2, -16.6869, -49.2648, "1", "Rua das Flores, 100"),
        delivery(3, -16.6900, -49.2648, "2", "Rua das Flores, 100"),
    ]

    stops = group_physical_stops(deliveries)

    assert len(stops) == 2


def test_different_addresses_nearby_stay_separate():
    deliveries = [
        delivery(2, -16.686900, -49.264800, "1", "Rua das Flores, 100"),
        delivery(3, -16.686905, -49.264805, "2", "Rua das Flores, 102"),
    ]

    stops = group_physical_stops(deliveries)

    assert len(stops) == 2


def test_invalid_tolerance_is_rejected():
    delivery_one = delivery(2, -16.6869, -49.2648, "1")

    try:
        group_physical_stops([delivery_one], address_tolerance_meters=-1)
    except ValueError as exc:
        assert "negative" in str(exc)
    else:
        raise AssertionError("negative tolerance should be rejected")
