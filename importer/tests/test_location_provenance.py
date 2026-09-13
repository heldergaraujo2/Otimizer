import pytest
from openpyxl import Workbook

from otimizer_importer.location import ResolvedLocation
from otimizer_importer.routing import TravelMetric
from otimizer_importer.service import optimize_deliveries_file


class FakeLocationProvider:
    def resolve(self, evidence):
        return ResolvedLocation(
            latitude=evidence.latitude + 0.001,
            longitude=evidence.longitude + 0.002,
            confidence=0.9,
            source="test-provider",
            property_latitude=evidence.latitude + 0.001,
            property_longitude=evidence.longitude + 0.002,
            access_latitude=evidence.latitude + 0.0015,
            access_longitude=evidence.longitude + 0.0025,
            cadastral_id="CAD-123",
        )


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(float(abs(row - col) * 100), float(abs(row - col) * 10)) for col in range(size))
            for row in range(size)
        )


def test_service_preserves_location_provenance_on_physical_stop(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
        "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
    ])
    sheet.append(["1", "1", "1", "TN-1", "Rua A, 10", "Centro", "Goiania", "74000-000", -16.70, -49.25])
    workbook.save(path)

    result = optimize_deliveries_file(
        str(path),
        routing_provider=FakeRoutingProvider(),
        location_provider=FakeLocationProvider(),
    )

    stop = result.physical_stops[0]
    assert stop.latitude == pytest.approx(-16.699)
    assert stop.longitude == pytest.approx(-49.248)
    assert stop.location_confidence == 0.9
    assert stop.location_source == "test-provider"
    assert stop.property_latitude == pytest.approx(-16.699)
    assert stop.property_longitude == pytest.approx(-49.248)
    assert stop.access_latitude == pytest.approx(-16.6985)
    assert stop.access_longitude == pytest.approx(-49.2475)
    assert stop.cadastral_id == "CAD-123"
    assert result.route.stops[0].physical_stop.location_source == "test-provider"
