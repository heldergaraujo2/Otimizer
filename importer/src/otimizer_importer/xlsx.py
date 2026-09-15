from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .address_parser import parse_address
from .models import Delivery, ImportResult


OPTIONAL_COLUMN_ALIASES = {
    "quadra": ("Quadra", "QUADRA", "quadra"),
    "lote": ("Lote", "LOTE", "lote"),
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coordinate(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not -90 <= number <= 90 or number == 0:
        return None
    return number


def _longitude(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not -180 <= number <= 180 or number == 0:
        return None
    return number


def _find_optional_column(columns: dict[str | None, int], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def import_result(path: str | Path) -> ImportResult:
    """Import an XLSX without requiring GPS columns.

    Latitude/Longitude are valuable evidence, but they are not mandatory for
    a delivery to enter the pipeline. Missing, zero, malformed or out-of-range
    coordinates become ``None`` so later location providers can use address,
    number, quadra, lote, CEP, neighborhood and city evidence.
    """
    workbook = load_workbook(filename=path, read_only=False, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            return ImportResult((), (), 0)

        columns = {_text(value): index for index, value in enumerate(header) if _text(value)}
        quadra_column = _find_optional_column(columns, OPTIONAL_COLUMN_ALIASES["quadra"])
        lote_column = _find_optional_column(columns, OPTIONAL_COLUMN_ALIASES["lote"])

        def get(row: tuple[Any, ...], name: str | None) -> Any:
            if name is None:
                return None
            index = columns.get(name)
            return row[index] if index is not None and index < len(row) else None

        deliveries: list[Delivery] = []
        unresolved: list[int] = []
        data_rows_seen = 0

        for row_number, row in enumerate(rows, start=2):
            if not any(_text(value) is not None for value in row):
                continue
            data_rows_seen += 1
            latitude = _coordinate(get(row, "Latitude"))
            longitude = _longitude(get(row, "Longitude"))

            address = _text(get(row, "Destination Address"))
            parsed = parse_address(address)
            quadra = _text(get(row, quadra_column)) or parsed.quadra
            lote = _text(get(row, lote_column)) or parsed.lote

            deliveries.append(
                Delivery(
                    row_number=row_number,
                    source_id=_text(get(row, "AT ID")),
                    source_sequence=_text(get(row, "Sequence")),
                    source_stop=_text(get(row, "Stop")),
                    tracking_number=_text(get(row, "SPX TN")),
                    address=address,
                    neighborhood=_text(get(row, "Bairro")),
                    city=_text(get(row, "City")),
                    zipcode=_text(get(row, "Zipcode/Postal code")),
                    latitude=latitude,
                    longitude=longitude,
                    quadra=quadra,
                    lote=lote,
                    number=parsed.number,
                    normalized_address=parsed.normalized,
                )
            )

        return ImportResult(tuple(deliveries), tuple(unresolved), data_rows_seen)
    finally:
        workbook.close()


def import_deliveries(path: str | Path) -> tuple[list[Delivery], list[int]]:
    """Backward-compatible import API returning deliveries and unresolved rows."""
    result = import_result(path)
    return list(result.deliveries), list(result.unresolved_rows)
