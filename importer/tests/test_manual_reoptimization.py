from openpyxl import Workbook

from otimizer_importer.location import LocationDataProvider, LocationEvidence, ResolvedLocation
from otimizer_importer.routing import TravelMetric
from otimizer_importer.service import optimize_deliveries_file


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size))
            for row in range(size)
        )


def write_workbook(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
        "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
    ])
    sheet.append(["1", "-", "-", "TN-1", "Rua A, 10", "Centro", "Goiania", "74000-000", -16.70, -49.25])
    sheet.append(["2", "-", "-", "TN-2", "Rua B, 20", "Centro", "Goiania", "74000-001", None, None])
    workbook.save(path)


class ParcelVariantProvider(LocationDataProvider):
    def __init__(self):
        self.calls = []

    def resolve(self, evidence: LocationEvidence):
        self.calls.append(evidence)
        if evidence.quadra == "30" and evidence.lote == "24" and evidence.neighborhood is None:
            return ResolvedLocation(
                latitude=-16.70,
                longitude=-49.25,
                confidence=0.90,
                source="parcel-without-neighborhood",
                property_latitude=-16.7005,
                property_longitude=-49.2505,
                access_latitude=-16.70,
                access_longitude=-49.25,
                cadastral_id="CAD-30-24",
            )
        return None


def test_service_retries_quadra_lote_without_neighborhood_when_provider_needs_exact_name(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
        "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude", "Quadra", "Lote",
    ])
    sheet.append(["1", "-", "-", "TN-1", "Rua SR 2, Sn", "Setor Recanto das Minas Gerais", "Goiania", "74785-540", None, None, "30", "24"])
    workbook.save(path)

    provider = ParcelVariantProvider()
    result = optimize_deliveries_file(str(path), routing_provider=FakeRoutingProvider(), location_provider=provider)

    assert result.pending_count == 0
    assert result.coverage_complete is True
    assert result.routing_complete is True
    assert result.route.physical_stop_count == 1
    stop = result.route.stops[0].physical_stop
    assert stop.location_source == "parcel-without-neighborhood"
    assert stop.cadastral_id == "CAD-30-24"
    assert any(e.neighborhood is None for e in provider.calls)


def test_manual_location_moves_pending_stop_into_full_optimization(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_workbook(path)
    provider = FakeRoutingProvider()

    before = optimize_deliveries_file(str(path), routing_provider=provider)
    assert before.pending_count == 1
    pending_stop = next(stop for stop in before.route.stops if stop.physical_stop.is_pending_location)

    manual_point = (-16.705, -49.255)
    after = optimize_deliveries_file(
        str(path),
        routing_provider=provider,
        manual_locations={pending_stop.id: manual_point},
    )

    assert after.pending_count == 0
    assert after.coverage_complete is True
    assert after.routing_complete is True
    assert after.route.delivery_count == before.route.delivery_count == 2
    assert after.route.physical_stop_count == before.route.physical_stop_count == 2
    manual_stop = next(stop for stop in after.route.stops if stop.physical_stop.id == pending_stop.id).physical_stop
    assert (manual_stop.latitude, manual_stop.longitude) == manual_point
    assert manual_stop.location_source == "manual"
    assert (manual_stop.access_latitude, manual_stop.access_longitude) == manual_point


def test_manual_location_only_changes_selected_stop_and_preserves_other_evidence(tmp_path):
    path = tmp_path / "deliveries.xlsx"
    write_workbook(path)
    result = optimize_deliveries_file(
        str(path),
        routing_provider=FakeRoutingProvider(),
        manual_locations={"stop-0002": (-16.706, -49.256)},
    )

    assert result.route.delivery_count == 2
    selected = next(stop for stop in result.route.stops if stop.physical_stop.id == "stop-0002").physical_stop
    assert selected.location_source == "manual"
    assert selected.latitude == -16.706
    assert selected.longitude == -49.256
    assert selected.deliveries[0].address == "Rua B, 20"
