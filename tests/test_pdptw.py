"""Tiny PDPTW using nonempty native pickup/delivery dictionaries.

The expected route is 0->1->2->0, length 6, within capacity 3 and
all time windows.  A deadline of 3 for the delivery is impossible.
"""

import grid
from .helpers import solve_compiled, served_customers

DISTANCES = {
    (0, 1): 2, (1, 0): 2,
    (0, 2): 2, (2, 0): 2,
    (1, 2): 2, (2, 1): 2,
}


def make_pdptw(*, delivery_deadline=20):
    model = grid.RoutingModel()
    model.add_vehicle_type(id=0, count=1, capacity=3)
    model.add_node(id=0, depot=True, tw_start=0, tw_end=30, service_t=0)
    model.add_node(id=1, pickup={"request": 2}, tw_start=0, tw_end=10,
                   service_t=0)
    model.add_node(id=2, delivery={"request": 2}, tw_start=0,
                   tw_end=delivery_deadline, service_t=0)
    for (u, v), distance in DISTANCES.items():
        model.add_edge(model.get_node(u), model.get_node(v),
                       distance=distance, travel_time=distance)
    model.set_objective(metric="distance")
    return model


def test_native_pdptw_known_optimum():
    converter, result = solve_compiled(make_pdptw())
    assert converter.node_data["commodities"] is not None
    assert any(type(manager).__name__ == "PickUpAndDeliveryManager"
               for manager in converter.managers)
    assert result["Optimal"] is True
    assert result["Cost"] == 6
    assert served_customers(result) == [1, 2]
    time = 0
    load = 0
    for u, v in zip([0, 1, 2], [1, 2, 0]):
        time += DISTANCES[u, v]
        assert time <= {0: 30, 1: 10, 2: 20}[v]
        if v == 1:
            load += 2
        elif v == 2:
            load -= 2
        assert 0 <= load <= 3


def test_pdptw_impossible_delivery_deadline():
    _, result = solve_compiled(make_pdptw(delivery_deadline=3))
    assert result["Cost"] is None
    assert result["Optimal"] is False
