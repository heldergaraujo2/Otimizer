from pathlib import Path

from openpyxl import Workbook

from otimizer_importer.stops import group_physical_stops
from otimizer_importer.xlsx import import_result


HEADERS = [
    "AT ID",
    "Sequence",
    "Stop",
    "SPX TN",
    "Destination Address",
    "Bairro",
    "City",
    "Zipcode/Postal code",
    "Latitude",
    "Longitude",
]


def write_xlsx(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def row(
    row_id: int,
    sequence: object,
    stop: object,
    tracking: str,
    latitude: object,
    longitude: object,
) -> list[object]:
    return [
        f"ID-{row_id}",
        sequence,
        stop,
        tracking,
        f"Endereço anonimizado {row_id}",
        "Bairro teste",
        "Cidade teste",
        "00000-000",
        latitude,
        longitude,
    ]


def test_real_world_case_missing_sequence_and_dash_values_keeps_every_valid_delivery(tmp_path: Path):
    path = tmp_path / "case_missing_sequence.xlsx"
    write_xlsx(
        path,
        [
            row(1, 1, 1, "TN-001", -16.700001, -49.200001),
            row(2, None, "-", "TN-002", -16.700001, -49.200001),
            row(3, "-", "-", "TN-003", -16.710001, -49.210001),
            row(4, 4, 2, "TN-004", None, -49.220001),
        ],
    )

    result = import_result(path)
    stops = group_physical_stops(list(result.deliveries))

    assert result.data_rows_seen == 4
    assert result.eligible_delivery_count == 3
    assert result.unresolved_rows == (5,)
    assert len(stops) == 2
    assert sum(stop.delivery_count for stop in stops) == 3
    assert {delivery.tracking_number for delivery in result.deliveries} == {
        "TN-001",
        "TN-002",
        "TN-003",
    }


def test_same_source_stop_at_different_coordinates_remains_two_physical_stops(tmp_path: Path):
    path = tmp_path / "case_same_stop_different_coordinates.xlsx"
    write_xlsx(
        path,
        [
            row(1, 1, "7", "TN-101", -16.700000, -49.200000),
            row(2, 2, "7", "TN-102", -16.710000, -49.210000),
        ],
    )

    result = import_result(path)
    stops = group_physical_stops(list(result.deliveries))

    assert result.eligible_delivery_count == 2
    assert len(stops) == 2
    assert [stop.delivery_count for stop in stops] == [1, 1]


def test_multiple_deliveries_at_one_location_are_one_routed_physical_stop(tmp_path: Path):
    path = tmp_path / "case_many_deliveries_one_location.xlsx"
    write_xlsx(
        path,
        [
            row(1, "-", "-", "TN-201", -16.700000, -49.200000),
            row(2, None, "-", "TN-202", -16.700000, -49.200000),
            row(3, None, None, "TN-203", -16.700000, -49.200000),
            row(4, 9, 9, "TN-204", -16.700000, -49.200000),
        ],
    )

    result = import_result(path)
    stops = group_physical_stops(list(result.deliveries))

    assert result.eligible_delivery_count == 4
    assert len(stops) == 1
    assert stops[0].delivery_count == 4
    assert len({delivery.tracking_number for delivery in stops[0].deliveries}) == 4
