from openpyxl import Workbook

from otimizer_importer.routing import TravelMetric
from otimizer_importer.service import optimize_deliveries_file


HEADERS = [
    "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
    "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
]


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(float(abs(row - col)), float(abs(row - col))) for col in range(size))
            for row in range(size)
        )


def write_xlsx(path, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def make_rows(count, *, same_location=False):
    rows = []
    for index in range(count):
        latitude = -16.70 if same_location else -16.70 + (index // 10) * 0.001
        longitude = -49.25 if same_location else -49.25 + (index % 10) * 0.001
        sequence = "-" if index % 11 == 0 else index + 1
        stop = "-" if index % 13 == 0 else (index // 2) + 1
        rows.append([
            str(index + 1), sequence, stop, f"TN-{index + 1:03d}",
            f"Endereço anonimizado {index + 1}", "Bairro teste", "Cidade teste",
            "00000-000", latitude, longitude,
        ])
    return rows


def test_125_and_131_delivery_exports_preserve_every_valid_delivery(tmp_path):
    provider = FakeRoutingProvider()

    for count in (125, 131):
        path = tmp_path / f"scale_{count}.xlsx"
        write_xlsx(path, make_rows(count))
        result = optimize_deliveries_file(str(path), routing_provider=provider)

        routed_rows = [
            delivery.row_number
            for route_stop in result.route.stops
            for delivery in route_stop.physical_stop.deliveries
        ]
        tracking_numbers = [
            delivery.tracking_number
            for route_stop in result.route.stops
            for delivery in route_stop.physical_stop.deliveries
        ]

        assert result.eligible_delivery_count == count
        assert result.pending_count == 0
        assert result.routed_delivery_count == count
        assert result.routed_stop_count == result.physical_stop_count
        assert result.coverage_complete is True
        assert sorted(routed_rows) == list(range(2, count + 2))
        assert len(routed_rows) == len(set(routed_rows))
        assert len(tracking_numbers) == count
        assert len(set(tracking_numbers)) == count
        assert [stop.sequence for stop in result.route.stops] == list(
            range(1, result.physical_stop_count + 1)
        )


def test_37_deliveries_at_one_coordinate_become_one_physical_stop(tmp_path):
    path = tmp_path / "single_location_37.xlsx"
    write_xlsx(path, make_rows(37, same_location=True))

    result = optimize_deliveries_file(str(path), routing_provider=FakeRoutingProvider())

    assert result.eligible_delivery_count == 37
    assert result.pending_count == 0
    assert result.physical_stop_count == 1
    assert result.routed_stop_count == 1
    assert result.routed_delivery_count == 37
    assert result.route.stops[0].sequence == 1
    assert result.route.stops[0].delivery_count == 37
    assert result.coverage_complete is True
    assert result.fully_resolved is True
