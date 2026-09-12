from otimizer_importer.models import Delivery
from otimizer_importer.stops import group_physical_stops


def test_every_delivery_appears_in_exactly_one_physical_stop():
    deliveries = [
        Delivery(2, "a", "-", "1", "TN-A", "A", None, "Cidade", None, -16.0, -49.0),
        Delivery(3, "b", None, None, "TN-B", "B", None, "Cidade", None, -16.0, -49.0),
        Delivery(4, "c", "9", "1", "TN-C", "C", None, "Cidade", None, -16.1, -49.1),
    ]

    stops = group_physical_stops(deliveries)
    flattened = [delivery for stop in stops for delivery in stop.deliveries]

    assert len(flattened) == len(deliveries)
    assert {d.row_number for d in flattened} == {2, 3, 4}
    assert len({id(d) for d in flattened}) == len(deliveries)
