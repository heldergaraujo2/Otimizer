from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from otimizer_importer.routing import TravelMetric
from otimizer_api.main import create_app


HEADERS = [
    "AT ID", "Sequence", "Stop", "SPX TN", "Destination Address",
    "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude",
]


class FakeRoutingProvider:
    def table(self, locations):
        size = len(locations)
        return tuple(
            tuple(
                TravelMetric(
                    float(abs(row - col)),
                    float(abs(row - col)),
                )
                for col in range(size)
            )
            for row in range(size)
        )


def workbook_bytes(count: int, *, physical_stop_count: int) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)

    for index in range(count):
        group = min(index, physical_stop_count - 1)
        latitude = -16.70 + (group // 10) * 0.001
        longitude = -49.25 + (group % 10) * 0.001
        sequence = "-" if index % 11 == 0 else index + 1
        stop = "-" if index % 13 == 0 else group + 1
        sheet.append([
            str(index + 1),
            sequence,
            stop,
            f"TN-{index + 1:03d}",
            f"Endereço anonimizado {index + 1}",
            "Bairro teste",
            "Cidade teste",
            "00000-000",
            latitude,
            longitude,
        ])

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_optimize_endpoint_preserves_realistic_scale_cases():
    client = TestClient(create_app(FakeRoutingProvider()))

    cases = [
        (37, 35),
        (125, 61),
        (131, 90),
    ]

    for delivery_count, expected_stop_count in cases:
        response = client.post(
            "/optimize",
            files={
                "file": (
                    f"scale_{delivery_count}.xlsx",
                    workbook_bytes(
                        delivery_count,
                        physical_stop_count=expected_stop_count,
                    ),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        summary = payload["summary"]

        assert summary["eligible_deliveries"] == delivery_count
        assert summary["routed_deliveries"] == delivery_count
        assert summary["physical_stops"] == expected_stop_count
        assert summary["routed_stops"] == expected_stop_count
        assert summary["pending"] == 0
        assert summary["coverage_complete"] is True

        route = payload["route"]
        assert [stop["sequence"] for stop in route] == list(
            range(1, expected_stop_count + 1)
        )
        assert sum(stop["delivery_count"] for stop in route) == delivery_count
        assert len({
            delivery["tracking_number"]
            for stop in route
            for delivery in stop["deliveries"]
        }) == delivery_count


def test_optimize_endpoint_preserves_many_deliveries_at_one_physical_stop():
    client = TestClient(create_app(FakeRoutingProvider()))
    response = client.post(
        "/optimize",
        files={
            "file": (
                "single_stop_37.xlsx",
                workbook_bytes(37, physical_stop_count=1),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    summary = payload["summary"]

    assert summary["eligible_deliveries"] == 37
    assert summary["routed_deliveries"] == 37
    assert summary["physical_stops"] == 1
    assert summary["routed_stops"] == 1
    assert summary["pending"] == 0
    assert summary["coverage_complete"] is True
    assert payload["route"][0]["sequence"] == 1
    assert payload["route"][0]["delivery_count"] == 37
    assert len(payload["route"][0]["deliveries"]) == 37
