from pathlib import Path

from openpyxl import Workbook

from otimizer_importer.routing import parse_osrm_table
from otimizer_importer.service import optimize_deliveries_file
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
]


def write_xlsx(path: Path, rows: list[list[object]], *, include_gps: bool = False) -> None:
    workbook = Workbook()
    sheet = workbook.active
    headers = HEADERS + (["Latitude", "Longitude"] if include_gps else [])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_xlsx_without_gps_columns_is_importable(tmp_path: Path):
    path = tmp_path / "without-gps.xlsx"
    write_xlsx(path, [["ID-1", 1, 1, "TN-1", "Rua A, 10", "Centro", "Cidade", "74000-000"]])

    result = import_result(path)

    assert result.data_rows_seen == 1
    assert result.eligible_delivery_count == 1
    assert result.deliveries[0].latitude is None
    assert result.deliveries[0].longitude is None


def test_zero_zero_gps_is_preserved_as_missing_location(tmp_path: Path):
    path = tmp_path / "zero-zero.xlsx"
    write_xlsx(
        path,
        [["ID-1", 1, 1, "TN-1", "Rua SR 2 qd 30 lt 24, Sn, qd 30 lt 24", "Setor A", "Goiania", "74000-000", 0, 0]],
        include_gps=True,
    )

    result = import_result(path)

    assert result.data_rows_seen == 1
    assert result.eligible_delivery_count == 1
    assert result.unresolved_rows == ()
    assert result.deliveries[0].latitude is None
    assert result.deliveries[0].longitude is None
    assert result.deliveries[0].quadra == "30"
    assert result.deliveries[0].lote == "24"


def test_all_pending_deliveries_remain_auditable_in_the_route(tmp_path: Path):
    path = tmp_path / "all-pending.xlsx"
    write_xlsx(
        path,
        [
            ["ID-1", 1, 1, "TN-1", "Rua sem coordenada, 10", "Cidade", "Cidade", "74000-000"],
            ["ID-2", 2, 2, "TN-2", "Outra rua sem coordenada, 20", "Cidade", "Cidade", "74000-000"],
        ],
    )

    result = optimize_deliveries_file(str(path))

    assert result.eligible_delivery_count == 2
    assert result.routed_delivery_count == 2
    assert result.physical_stop_count == 2
    assert result.routed_stop_count == 2
    assert result.pending_count == 2
    assert result.unresolved_rows == (2, 3)
    assert result.routing_complete is False
    assert result.coverage_complete is True
    assert result.route_metrics.distance_meters == 0
    assert result.route_metrics.duration_seconds == 0
    assert len(result.route_metrics.legs) == 1
    assert result.route_metrics.legs[0].routable is False


def test_nan_metric_becomes_unavailable_edge_instead_of_fatal_error():
    payload = '{"code":"Ok","distances":[[0,NaN],[100,0]],"durations":[[0,5],[7,0]]}'

    matrix = parse_osrm_table(payload, expected_size=2)

    assert matrix[0][0] is not None
    assert matrix[0][1] is None
    assert matrix[1][0] is not None
    assert matrix[1][1] is not None


def test_negative_metric_becomes_unavailable_edge_instead_of_fatal_error():
    payload = '{"code":"Ok","distances":[[0,-1],[100,0]],"durations":[[0,5],[7,0]]}'

    matrix = parse_osrm_table(payload, expected_size=2)

    assert matrix[0][1] is None
