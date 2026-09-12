from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .models import Delivery


REQUIRED_COLUMNS = {
    "Latitude",
    "Longitude",
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
    if not -90 <= number <= 90:
        return None
    return number


def _longitude(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not -180 <= number <= 180:
        return None
    return number


def import_deliveries(path: str | Path) -> tuple[list[Delivery], list[int]]:
    """Import every row with valid latitude and longitude.

    Returns (eligible deliveries, unresolved spreadsheet row numbers).
    Source Sequence/Stop values are retained only as metadata.
    """
    workbook = load_workbook(filename=path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            return [], []

        columns = {_text(value): index for index, value in enumerate(header) if _text(value)}
        missing = REQUIRED_COLUMNS - columns.keys()
        if missing:
            raise ValueError(f"Colunas obrigatórias ausentes: {sorted(missing)}")

        def get(row: tuple[Any, ...], name: str) -> Any:
            index = columns.get(name)
            return row[index] if index is not None and index < len(row) else None

        deliveries: list[Delivery] = []
        unresolved: list[int] = []

        for row_number, row in enumerate(rows, start=2):
            latitude = _coordinate(get(row, "Latitude"))
            longitude = _longitude(get(row, "Longitude"))
            if latitude is None or longitude is None:
                unresolved.append(row_number)
                continue

            deliveries.append(
                Delivery(
                    row_number=row_number,
                    source_id=_text(get(row, "AT ID")),
                    source_sequence=_text(get(row, "Sequence")),
                    source_stop=_text(get(row, "Stop")),
                    tracking_number=_text(get(row, "SPX TN")),
                    address=_text(get(row, "Destination Address")),
                    neighborhood=_text(get(row, "Bairro")),
                    city=_text(get(row, "City")),
                    zipcode=_text(get(row, "Zipcode/Postal code")),
                    latitude=latitude,
                    longitude=longitude,
                )
            )

        return deliveries, unresolved
    finally:
        workbook.close()
