from pathlib import Path

import pytest

from otimizer_importer.stops import group_physical_stops
from otimizer_importer.xlsx import import_result


ROOT = Path(__file__).resolve().parents[2]

REAL_EXPORTS = (
    pytest.param(
        ROOT / "12-09-2026 JOSE CARVALHO DE ARAUJO NETO.xlsx",
        125,
        61,
        id="12-09-2026-125-deliveries",
    ),
    pytest.param(
        ROOT / "11-09-2026 JOSE CARVALHO DE ARAUJO NETO.xlsx",
        131,
        90,
        id="11-09-2026-131-deliveries",
    ),
    pytest.param(
        ROOT / "(1)12-09-2026 JOSE CARVALHO DE ARAUJO NETO.xlsx",
        37,
        35,
        id="12-09-2026-37-deliveries",
    ),
)


@pytest.mark.parametrize("path,delivery_count,physical_stop_count", REAL_EXPORTS)
def test_real_xlsx_exports_preserve_delivery_accounting(
    path: Path,
    delivery_count: int,
    physical_stop_count: int,
):
    assert path.exists(), f"Regression XLSX fixture not found: {path}"

    result = import_result(path)
    stops = group_physical_stops(list(result.deliveries))

    assert result.data_rows_seen == delivery_count
    assert len(result.deliveries) == delivery_count
    assert result.unresolved_rows == ()
    assert len(stops) == physical_stop_count
    assert sum(len(stop.deliveries) for stop in stops) == delivery_count
    assert all(stop.deliveries for stop in stops)
    assert len({delivery.row_number for delivery in result.deliveries}) == delivery_count
