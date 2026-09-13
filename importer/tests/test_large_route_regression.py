from openpyxl import Workbook

from otimizer_importer.routing import TravelMetric
from otimizer_importer.service import optimize_deliveries_file


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(
                TravelMetric(
                    100.0 * abs(row - col),
                    10.0 * abs(row - col),
                )
                for col in range(size)
            )
            for row in range(size)
        )


def test_service_scales_to_100_physical_stops_without_losing_coverage(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
        "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
    ])
    for index in range(100):
        sheet.append([
            str(index),
            str(100 - index),
            str(index % 7),
            f"TN-{index}",
            f"Rua {index}",
            "Centro",
            "Goiania",
            f"74000-{index:03d}",
            -16.70 - index * 0.0001,
            -49.25 - index * 0.0001,
        ])
    path = tmp_path / "large-route.xlsx"
    workbook.save(path)

    result = optimize_deliveries_file(
        str(path),
        routing_provider=FakeRoutingProvider(),
    )

    assert result.eligible_delivery_count == 100
    assert result.pending_count == 0
    assert result.physical_stop_count == 100
    assert result.routed_stop_count == 100
    assert result.routed_delivery_count == 100
    assert result.coverage_complete is True
    assert [stop.sequence for stop in result.route.stops] == list(range(1, 101))
    assert len({
        delivery.row_number
        for stop in result.route.stops
        for delivery in stop.physical_stop.deliveries
    }) == 100
