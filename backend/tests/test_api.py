from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from otimizer_importer.routing import TravelMetric
from otimizer_api.main import create_app


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size))
            for row in range(size)
        )


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


def test_optimize_rejects_invalid_endpoint_pair():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"origin_latitude": "-16.70"},
    )
    assert response.status_code == 422
    assert "both latitude and longitude" in response.json()["detail"]
