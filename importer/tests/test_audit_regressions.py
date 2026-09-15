from openpyxl import Workbook

from otimizer_importer.models import Delivery, PhysicalStop
from otimizer_importer.optimization import OptimizationObjective, OptimizationProblem, RouteEndpoint, optimize
from otimizer_importer.routing import TravelMetric
from otimizer_importer.xlsx import import_result


def _stop(index: int) -> PhysicalStop:
    return PhysicalStop(
        id=f"stop-{index}",
        latitude=-16.70 - index * 0.001,
        longitude=-49.20 - index * 0.001,
        deliveries=[Delivery(index + 1, None, None, None, f"TN-{index}", f"Rua {index}, {index + 1}", None, "Goiânia", "74000-000", -16.70, -49.20)],
    )


def test_origin_multistart_does_not_drop_last_reachable_start_candidate():
    size = 13
    stops = tuple(_stop(index) for index in range(size))
    matrix = [[TravelMetric(100, 100) if row != col else TravelMetric(0, 0) for col in range(size)] for row in range(size)]
    matrix[12][0] = TravelMetric(1, 1)
    for index in range(11):
        matrix[index][index + 1] = TravelMetric(1, 1)

    origin = RouteEndpoint(-16.69, -49.19, "depot")
    origin_metrics = tuple(TravelMetric(1 if index == 0 else 2, 1 if index == 0 else 2) for index in range(size))
    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        origin=origin,
        origin_metrics=origin_metrics,
        objective=OptimizationObjective.TIME,
    )

    result = optimize(problem)

    assert result.route.stops[0].id == "stop-12"
    assert result.origin_metric == TravelMetric(2, 2)
    assert result.route.physical_stop_count == size


def test_two_opt_with_destination_can_improve_by_moving_final_stop():
    size = 11
    stops = tuple(_stop(index) for index in range(size))
    matrix = [[TravelMetric(100, 100) if row != col else TravelMetric(0, 0) for col in range(size)] for row in range(size)]
    for index in range(9):
        matrix[index][index + 1] = TravelMetric(1, 1)
    matrix[9][10] = TravelMetric(50, 50)
    matrix[9][1] = TravelMetric(1, 1)
    matrix[10][2] = TravelMetric(1, 1)

    destination = RouteEndpoint(-16.85, -49.25, "customer")
    destination_metrics = tuple(TravelMetric(1, 1) if index == 10 else TravelMetric(100, 100) for index in range(size))
    problem = OptimizationProblem(
        stops=stops,
        matrix=tuple(tuple(row) for row in matrix),
        destination=destination,
        destination_metrics=destination_metrics,
        objective=OptimizationObjective.TIME,
    )

    result = optimize(problem)

    assert result.route.stops[-1].id == "stop-10"
    assert result.destination_metric == TravelMetric(1, 1)


def test_empty_route_with_endpoints_returns_empty_result():
    origin = RouteEndpoint(-16.69, -49.19, "depot")
    destination = RouteEndpoint(-16.85, -49.25, "customer")
    problem = OptimizationProblem.from_full_matrix(
        (),
        (
            (TravelMetric(0, 0), TravelMetric(10, 10)),
            (TravelMetric(10, 10), TravelMetric(0, 0)),
        ),
        origin=origin,
        destination=destination,
    )

    result = optimize(problem)

    assert result.route.physical_stop_count == 0
    assert result.origin_metric is None
    assert result.destination_metric is None


def test_xlsx_blank_rows_are_not_imported_as_deliveries(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["AT ID", "Sequence", "Stop", "SPX TN", "Destination Address", "Bairro", "City", "Zipcode/Postal code", "Latitude", "Longitude"])
    sheet.append(["a", "1", "1", "TN-1", "Rua A, 10", "Centro", "Goiânia", "74000-000", -16.7, -49.2])
    sheet.append([None] * 10)
    sheet.append(["b", "2", "2", "TN-2", "Rua B, 20", "Centro", "Goiânia", "74000-000", -16.71, -49.21])
    path = tmp_path / "blank-row.xlsx"
    workbook.save(path)
    workbook.close()

    result = import_result(path)

    assert result.data_rows_seen == 2
    assert result.eligible_delivery_count == 2
    assert [delivery.row_number for delivery in result.deliveries] == [2, 4]
