import grid
from .helpers import compile_model


def make_non_pd_model():
    model = grid.RoutingModel()
    model.add_vehicle_type(id=0, count=1)  # no native capacity, as in ECVRP
    depot = model.add_node(id=0, depot=True)
    customer = model.add_node(id=1)
    model.add_edge(depot, customer, distance=2)
    model.add_edge(customer, depot, distance=2)
    model.set_objective(metric="distance")
    return model, depot, customer


def test_omitted_pickup_delivery_remain_none():
    model, depot, customer = make_non_pd_model()
    for node in (depot, customer):
        assert node.pickup is None
        assert node.delivery is None


def test_explicit_pickup_delivery_are_preserved():
    model = grid.RoutingModel()
    pickup = {"request": 2}
    delivery = {"request": 2}
    n1 = model.add_node(id=1, pickup=pickup)
    n2 = model.add_node(id=2, delivery=delivery)
    assert n1.pickup == pickup and n1.delivery is None
    assert n2.delivery == delivery and n2.pickup is None


def test_explicit_empty_dict_is_not_coerced_to_none():
    # This merely documents the restored old semantics; it does NOT
    # require the converter to treat an explicit empty dict as absence.
    model = grid.RoutingModel()
    node = model.add_node(id=1, pickup={}, delivery={})
    assert node.pickup == {}
    assert node.delivery == {}


def test_no_pd_and_no_native_capacity_compiles():
    model, _, _ = make_non_pd_model()
    converter = compile_model(model)
    assert converter.node_data["commodities"] is None
    assert converter.vehicle_data["pd_capacities"] is None
    assert not any(type(manager).__name__ == "PickUpAndDeliveryManager"
                   for manager in converter.managers)


def test_no_pd_solve_public_api():
    model, _, _ = make_non_pd_model()
    result = model.solve(solver="CABS", time_limit=20)
    assert result["Optimal"] is True
    assert result["Cost"] == 4
    assert result["Solution"] == [[1]]
