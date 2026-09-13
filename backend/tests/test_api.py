from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from otimizer_importer.routing import TravelMetric
from otimizer_api.main import create_app

# Existing API regression suite: invalid provider matrices are routing failures,
# therefore the public endpoint exposes them as 502 Bad Gateway.


def test_optimize_maps_inconsistent_routing_matrix_to_unprocessable_entity():
    client = TestClient(create_app(InconsistentRoutingProvider()))
    response = post_workbook(client, workbook_bytes())
    assert response.status_code == 502
    assert "routing matrix size" in response.json()["detail"]
