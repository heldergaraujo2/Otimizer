from openpyxl import Workbook

from otimizer_importer.location import LocationDataProvider, LocationEvidence, ResolvedLocation
from otimizer_importer.routing import TravelMetric
from otimizer_importer.service import optimize_deliveries_file


class FakeRoutingProvider:
    def __init__(self):
        self.locations = None

    def table(self, locations):
        self.locations = list(locations)
        size = len(self.locations)
        return tuple(
            tuple(TravelMetric(100.0 * abs(row - col), 10.0 * abs(row - col)) for col in range(size))
            for row in range(size)
        )


class FakeLocationProvider(LocationDataProvider):
    def __init__(self):
        self.calls = []

    def resolve(self, evidence: LocationEvidence):
        self.calls.append(evidence)
        return ResolvedLocation(
            latitude=evidence.latitude + 0.001,
            longitude=evidence.longitude + 0.001,
            confidence=0.9,
            source="fake",
        )


def write_xlsx(path, rows=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
        "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
    ])
    rows = rows or [
        ["1", "1", "1", "TN-1", "Rua A", "Centro", "Goiania", "74000-000", -16.70, -49.25],
        ["2", "-", "-", "TN-2", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
        ["3", "2", "2", "TN-3", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
    ]
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_service_preserves_deliveries_and_groups_physical_stops(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_xlsx(path)
    provider = FakeRoutingProvider()

    result = optimize_deliveries_file(str(path), routing_provider=provider)

    assert result.eligible_delivery_count == 3
    assert result.pending_count == 0
    assert result.physical_stop_count == 2
    assert result.route.delivery_count == 3
    assert result.route.physical_stop_count == 2
    assert [stop.sequence for stop in result.route.stops] == [1, 2]
    assert [stop.delivery_count for stop in result.route.stops] == [1, 2]
    assert len(provider.locations) == 2


def test_service_reports_unresolved_rows_without_dropping_them(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_xlsx(path)
    workbook = __import__("openpyxl").load_workbook(path)
    sheet = workbook.active
    sheet.append(["4", "3", "3", "TN-4", "Rua C", "Centro", "Goiania", "74000-002", None, -49.27])
    workbook.save(path)

    result = optimize_deliveries_file(str(path), routing_provider=FakeRoutingProvider())

    assert result.eligible_delivery_count == 4
    assert result.pending_count == 1
    assert result.unresolved_rows == (5,)
    assert result.route.delivery_count == 4
    assert result.routed_delivery_count == 4
    assert result.coverage_complete is True
    assert result.routing_complete is False


def test_service_route_contains_each_valid_delivery_row_exactly_once(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_xlsx(path, [
        ["1", "90", "7", "TN-1", "Rua A", "Centro", "Goiania", "74000-000", -16.70, -49.25],
        ["2", "-", "-", "TN-2", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
        ["3", "10", "3", "TN-3", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
        ["4", "2", "99", "TN-4", "Rua C", "Centro", "Goiania", "74000-002", -16.72, -49.27],
    ])

    result = optimize_deliveries_file(str(path), routing_provider=FakeRoutingProvider())
    routed_rows = [
        delivery.row_number
        for route_stop in result.route.stops
        for delivery in route_stop.physical_stop.deliveries
    ]

    assert result.eligible_delivery_count == 4
    assert result.route.delivery_count == 4
    assert sorted(routed_rows) == [2, 3, 4, 5]
    assert len(routed_rows) == len(set(routed_rows))
    assert result.physical_stop_count == 3
    assert result.route.physical_stop_count == 3
    assert {stop.id for stop in result.physical_stops} == {stop.id for stop in result.route.stops}


def test_service_ignores_sequence_and_stop_for_delivery_coverage(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_xlsx(path, [
        ["1", "-", "-", "TN-1", "Rua A", "Centro", "Goiania", "74000-000", -16.70, -49.25],
        ["2", "99", "88", "TN-2", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
        ["3", "1", "1", "TN-3", "Rua C", "Centro", "Goiania", "74000-002", -16.72, -49.27],
    ])

    result = optimize_deliveries_file(str(path), routing_provider=FakeRoutingProvider())
    tracking_numbers = {
        delivery.tracking_number
        for stop in result.route.stops
        for delivery in stop.physical_stop.deliveries
    }

    assert tracking_numbers == {"TN-1", "TN-2", "TN-3"}
    assert result.route.delivery_count == 3
    assert result.route.physical_stop_count == 3
    assert [stop.sequence for stop in result.route.stops] == [1, 2, 3]


def test_service_resolves_each_unique_location_evidence_only_once(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_xlsx(path)
    location_provider = FakeLocationProvider()

    result = optimize_deliveries_file(
        str(path),
        routing_provider=FakeRoutingProvider(),
        location_provider=location_provider,
    )

    assert result.route.delivery_count == 3
    assert len(location_provider.calls) == 2
    assert len({
        (e.latitude, e.longitude, e.normalized_address, e.number, e.quadra, e.lote, e.zipcode, e.neighborhood, e.city)
        for e in location_provider.calls
    }) == 2
    assert all(stop.location_source == "fake" for stop in result.physical_stops)
