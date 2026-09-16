from fastapi.testclient import TestClient

from otimizer_importer.routing import TravelMetric
from otimizer_api.main import create_app


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size))
            for row in range(size)
        )


def test_manual_route_accepts_address_and_optional_map_points():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize-manual",
        json={
            "objective": "time",
            "stops": [
                {"street": "Rua A", "number": "10", "neighborhood": "Centro", "city": "Goiania"},
                {"street": "Rua B", "number": "20", "neighborhood": "Centro", "city": "Goiania", "latitude": -16.70, "longitude": -49.25},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["routed_deliveries"] == 2
    assert payload["summary"]["routed_stops"] == 2
    assert payload["summary"]["coverage_complete"] is True
    assert payload["summary"]["pending"] == 0


def test_manual_route_rejects_missing_location_data():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post("/optimize-manual", json={"stops": [{"neighborhood": "Centro"}]})
    assert response.status_code == 422
    assert "rua/endereço" in response.json()["detail"]


def test_manual_route_rejects_partial_coordinates():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize-manual",
        json={"stops": [{"street": "Rua A", "latitude": -16.70}]},
    )
    assert response.status_code == 422
    assert "latitude e longitude juntas" in response.json()["detail"]
