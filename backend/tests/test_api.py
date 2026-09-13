from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from otimizer_importer.location import ResolvedLocation
from otimizer_importer.routing import RoutingError, TravelMetric
from otimizer_api.main import create_app


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size))
            for row in range(size)
        )


class FakeLocationProvider:
    def resolve(self, evidence):
        return ResolvedLocation(
            latitude=-16.701,
            longitude=-49.251,
            confidence=0.96,
            source="test-resolved-location",
            property_latitude=-16.7015,
            property_longitude=-49.2515,
            access_latitude=-16.701,
            access_longitude=-49.251,
            cadastral_id="CAD-TEST-1",
        )


class FailingRoutingProvider:
    def table(self, locations):
        raise RoutingError("routing service unavailable")


class InconsistentRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(1000, 60) for _ in range(size - 1))
            for _ in range(size)
        )


class UnreachableRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(None if row != col else TravelMetric(0, 0) for col in range(size))
            for row in range(size)
        )


def workbook_bytes(rows=None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["AT ID", "Sequence", "Stop", "SPX TN", "Destination Address", "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude"])
    if rows is None:
        rows = [
            ["1", "-", "-", "TN-1", "Rua A", "Centro", "Goiania", "74000-000", -16.70, -49.25],
            ["2", "2", "9", "TN-2", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
            ["3", "1", "1", "TN-3", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26],
        ]
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def post_workbook(client, content, provider=None):
    return client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_health():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_returns_frontend_ready_route_result():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = post_workbook(client, workbook_bytes())

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["eligible_deliveries"] == 3
    assert payload["summary"]["routed_deliveries"] == 3
    assert payload["summary"]["physical_stops"] == 2
    assert payload["summary"]["routed_stops"] == 2
    assert payload["summary"]["pending"] == 0
    assert payload["summary"]["coverage_complete"] is True
    assert [stop["sequence"] for stop in payload["route"]] == [1, 2]
    assert [stop["delivery_count"] for stop in payload["route"]] == [1, 2]
    assert len(payload["legs"]) == 1


def test_optimize_serializes_resolved_location_provenance():
    client = TestClient(create_app(FakeRoutingProvider(), location_provider=FakeLocationProvider()))
    response = post_workbook(client, workbook_bytes())

    assert response.status_code == 200
    locations = [stop["location"] for stop in response.json()["route"]]
    assert all(location["source"] == "test-resolved-location" for location in locations)
    assert all(location["confidence"] == 0.96 for location in locations)
    assert all(location["property_latitude"] == -16.7015 for location in locations)
    assert all(location["property_longitude"] == -49.2515 for location in locations)
    assert all(location["access_latitude"] == -16.701 for location in locations)
    assert all(location["access_longitude"] == -49.251 for location in locations)
    assert all(location["cadastral_id"] == "CAD-TEST-1" for location in locations)


def test_optimize_includes_endpoint_leg_and_all_stop_deliveries():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"origin_latitude": "-16.69", "origin_longitude": "-49.24", "destination_latitude": "-16.72", "destination_longitude": "-49.27"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["legs"]) == 3
    assert payload["legs"][0]["from_id"] == "origin"
    assert payload["legs"][-1]["to_id"] == "destination"
    assert [delivery["tracking_number"] for delivery in payload["route"][1]["deliveries"]] == ["TN-2", "TN-3"]


def test_optimize_rejects_invalid_endpoint_pair():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"origin_latitude": "-16.70"},
    )
    assert response.status_code == 422
    assert "both latitude and longitude" in response.json()["detail"]


def test_optimize_rejects_workbook_without_valid_coordinates():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = post_workbook(client, workbook_bytes([
        ["1", "-", "-", "TN-1", "Rua A", "Centro", "Goiania", "74000-000", None, -49.25],
        ["2", "-", "-", "TN-2", "Rua B", "Centro", "Goiania", "74000-001", "invalid", None],
    ]))
    assert response.status_code == 422
    assert "no deliveries with valid latitude and longitude" in response.json()["detail"]


def test_optimize_handles_all_deliveries_at_one_physical_stop():
    client = TestClient(create_app(FakeRoutingProvider()))
    rows = [
        [str(index), "-", "-", f"TN-{index}", "Rua Unica", "Centro", "Goiania", "74000-000", -16.70, -49.25]
        for index in range(1, 38)
    ]
    response = post_workbook(client, workbook_bytes(rows))
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["eligible_deliveries"] == 37
    assert payload["summary"]["routed_deliveries"] == 37
    assert payload["summary"]["physical_stops"] == 1
    assert payload["summary"]["routed_stops"] == 1
    assert payload["summary"]["pending"] == 0
    assert payload["summary"]["coverage_complete"] is True
    assert [stop["sequence"] for stop in payload["route"]] == [1]
    assert payload["route"][0]["delivery_count"] == 37
    assert payload["summary"]["distance_meters"] == 0
    assert payload["summary"]["duration_seconds"] == 0


def test_optimize_maps_inconsistent_routing_matrix_to_bad_gateway():
    client = TestClient(create_app(InconsistentRoutingProvider()))
    response = post_workbook(client, workbook_bytes())
    assert response.status_code == 502
    assert "Routing provider failed" in response.json()["detail"]
    assert "invalid size" in response.json()["detail"]


def test_optimize_maps_unreachable_route_to_unprocessable_entity():
    client = TestClient(create_app(UnreachableRoutingProvider()))
    response = post_workbook(client, workbook_bytes())
    assert response.status_code == 422
    assert "complete road-network route" in response.json()["detail"]


def test_optimize_maps_routing_failure_to_bad_gateway():
    client = TestClient(create_app(FailingRoutingProvider()))
    response = post_workbook(client, workbook_bytes())
    assert response.status_code == 502
    assert "Routing provider failed" in response.json()["detail"]


def test_optimize_rejects_oversized_upload(monkeypatch):
    monkeypatch.setenv("OTIMIZER_MAX_UPLOAD_BYTES", "100")
    client = TestClient(create_app(FakeRoutingProvider()))
    response = post_workbook(client, workbook_bytes())
    assert response.status_code == 413
    assert "byte limit" in response.json()["detail"]


def test_optimize_rejects_destination_with_return_to_start():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={
            "destination_latitude": "-16.72",
            "destination_longitude": "-49.27",
            "return_to_start": "true",
        },
    )
    assert response.status_code == 422
    assert "cannot be combined" in response.json()["detail"]


def test_cors_origins_are_configurable(monkeypatch):
    monkeypatch.setenv("OTIMIZER_CORS_ORIGINS", "https://app.example.com, https://admin.example.com")
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.options(
        "/optimize",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
