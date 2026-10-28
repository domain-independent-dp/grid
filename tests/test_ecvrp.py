"""Small ECVRP-style model with custom load/battery variables.

This is a synthetic regression test, NOT the full ECVRP from the paper.
Only 0->1->2->0 is feasible when recharge is enabled; its cost is 9.
"""

import pytest
import grid
from .helpers import solve_compiled, served_customers

ARCS = {(0, 1): 4, (1, 0): 4, (1, 2): 1, (2, 0): 4}


def make_ecvrp(*, allow_charging=True):
    model = grid.RoutingModel(triangular_inequality=False)
    vehicle = model.add_vehicle_type(id=0, count=1)  # no native capacity!
    load = vehicle.add_integer_var(2)
    battery = vehicle.add_float_var(5.0, "high")
    stations_left = vehicle.add_nodes_set_var({2})
    model.add_node(id=0, depot=True)
    customer = model.add_node(id=1)
    customer.add_constraint(load >= 1)
    customer.add_transition(load, load - 1)
    station = model.add_node(id=2, optional=True, max_visits=1)
    station.add_constraint(stations_left.contains(2))
    station.add_transition(stations_left, stations_left.remove(2))
    if allow_charging:
        station.add_transition(battery, 5.0)
    for (u, v), distance in ARCS.items():
        edge = model.add_edge(model.get_node(u), model.get_node(v), distance=distance)
        edge.add_constraint(battery >= distance)
        if v != 2 or not allow_charging:
            edge.add_transition(battery, battery - distance)
    model.set_objective(metric="distance")
    return model


def test_ecvrp_recharge_needed():
    converter, result = solve_compiled(make_ecvrp())
    assert converter.node_data["commodities"] is None
    assert converter.vehicle_data["pd_capacities"] is None
    assert result["Optimal"] is True
    assert result["Cost"] == pytest.approx(9)
    assert served_customers(result) == [1, 2]
    charge = 5.0
    for u, v in zip([0, 1, 2], [1, 2, 0]):
        charge -= ARCS[u, v]
        assert charge >= -1e-9
        if v == 2:
            charge = 5.0


def test_ecvrp_without_recharge_infeasible():
    _, result = solve_compiled(make_ecvrp(allow_charging=False))
    assert result["Cost"] is None
    assert result["Optimal"] is False
