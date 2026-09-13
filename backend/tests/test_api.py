from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from otimizer_importer.routing import RoutingError, TravelMetric
from otimizer_api.main import create_app


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size))
            for row in range(size)
        )


class FailingRoutingProvider:
    def table(self, locations):
        raise RoutingError("routing service unavailable")


def workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["AT ID", "Sequence", "Stop", "SPX TN", "Destination Address", "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude"])
    sheet.append(["1", "-", "-", "TN-1", "Rua A", "Centro", "Goiania", "74000-000", -16.70, -49.25])
    sheet.append(["2", "2", "9", "TN-2", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26])
    sheet.append(["3", "1", "1", "TN-3", "Rua B", "Centro", "Goiania", "74000-001", -16.71, -49.26])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_health():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_returns_frontend_ready_route_result():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"objective": "time"},
    )

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


def test_optimize_maps_routing_failure_to_bad_gateway():
    client = TestClient(create_app(FailingRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 502
    assert "Routing provider failed" in response.json()["detail"]


def test_optimize_rejects_oversized_upload(monkeypatch):
    monkeypatch.setenv("OTIMIZER_MAX_UPLOAD_BYTES", "100")
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 413
    assert "byte limit" in response.json()["detail"]


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
