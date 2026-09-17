import json
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
    sheet.append([
        "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
        "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
    ])
    sheet.append(["1", "-", "-", "TN-1", "Rua A, 10", "Centro", "Goiania", "74000-000", -16.70, -49.25])
    sheet.append(["2", "-", "-", "TN-2", "Rua B, 20", "Centro", "Goiania", "74000-001", None, None])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def post(client, manual_locations=None):
    data = {}
    if manual_locations is not None:
        data["manual_locations"] = json.dumps(manual_locations)
    return client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data=data,
    )


def test_api_reoptimizes_full_route_after_manual_stop_location():
    client = TestClient(create_app(FakeRoutingProvider()))

    before = post(client)
    assert before.status_code == 200
    before_payload = before.json()
    assert before_payload["summary"]["pending"] == 1
    assert before_payload["summary"]["coverage_complete"] is True

    after = post(client, [{"stop_id": "stop-0002", "latitude": -16.705, "longitude": -49.255}])
    assert after.status_code == 200
    payload = after.json()
    assert payload["summary"]["pending"] == 0
    assert payload["summary"]["coverage_complete"] is True
    assert payload["summary"]["routing_complete"] is True
    assert payload["summary"]["routed_deliveries"] == 2
    assert payload["summary"]["routed_stops"] == 2
    manual = next(stop for stop in payload["route"] if stop["id"] == "stop-0002")
    assert manual["location"]["source"] == "manual"
    assert manual["latitude"] == -16.705
    assert manual["longitude"] == -49.255
    assert manual["location"]["access_latitude"] == -16.705
    assert manual["location"]["access_longitude"] == -49.255


def test_api_rejects_invalid_manual_location_payload():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"manual_locations": "not-json"},
    )
    assert response.status_code == 422
    assert "valid JSON" in response.json()["detail"]


def test_api_rejects_zero_zero_manual_location():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = post(client, [{"stop_id": "stop-0002", "latitude": 0, "longitude": 0}])
    assert response.status_code == 422
    assert "invalid coordinates" in response.json()["detail"]


def test_api_rejects_unknown_manual_stop():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = post(client, [{"stop_id": "stop-9999", "latitude": -16.705, "longitude": -49.255}])
    assert response.status_code == 422
    assert "unknown stop" in response.json()["detail"]
