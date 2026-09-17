from io import BytesIO
import json

from fastapi.testclient import TestClient
from openpyxl import Workbook

from otimizer_api.main import create_app


class FakeRoutingProvider:
    pass


def workbook_bytes():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["stop_id", "latitude", "longitude"])
    sheet.append(["stop-0002", -16.7, -49.2])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def post(client, locations):
    return client.post(
        "/optimize",
        files={"file": ("deliveries.xlsx", workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"manual_locations": json.dumps(locations)},
    )


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
