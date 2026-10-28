"""Tiny, exactly solvable CVRP tests using native demand/capacity."""

import grid
from .helpers import solve_compiled, served_customers

DISTANCES = {
    (0, 1): 4, (1, 0): 4,
    (0, 2): 6, (2, 0): 6,
    (1, 2): 3, (2, 1): 3,
}


def make_cvrp(*, capacity):
    model = grid.RoutingModel()
    model.add_vehicle_type(id=0, count=1, capacity=capacity)
    model.add_node(id=0, depot=True)
    model.add_node(id=1, demand=3)
    model.add_node(id=2, demand=5)
    for (u, v), distance in DISTANCES.items():
        model.add_edge(model.get_node(u), model.get_node(v), distance=distance)
    model.set_objective(metric="distance")
    return model


def test_cvrp_one_vehicle_known_optimum():
    converter, result = solve_compiled(make_cvrp(capacity=8))
    assert converter.node_data["commodities"] is None
    assert result["Optimal"] is True
    assert result["Cost"] == 13
    assert sorted(served_customers(result)) == [1, 2]
    assert len([route for route in result["Solution"] if route]) == 1
    route = result["Solution"][0]
    assert sum(DISTANCES[u, v] for u, v in zip([0] + route, route + [0])) == 13
    assert 3 + 5 <= 8


def test_cvrp_insufficient_capacity_is_infeasible():
    _, result = solve_compiled(make_cvrp(capacity=7))
    assert result["Cost"] is None
    assert result["Optimal"] is False
