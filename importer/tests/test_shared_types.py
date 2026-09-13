from otimizer_importer.optimization import OptimizationObjective, RouteEndpoint
from otimizer_importer.optimizer import OptimizationObjective as GreedyOptimizationObjective
from otimizer_importer.routing import RouteEndpoint as RoutingRouteEndpoint
from otimizer_importer.types import OptimizationObjective as CanonicalOptimizationObjective
from otimizer_importer.types import RouteEndpoint as CanonicalRouteEndpoint


def test_shared_types_have_one_canonical_identity():
    assert OptimizationObjective is CanonicalOptimizationObjective
    assert GreedyOptimizationObjective is CanonicalOptimizationObjective
    assert RouteEndpoint is CanonicalRouteEndpoint
    assert RoutingRouteEndpoint is CanonicalRouteEndpoint
