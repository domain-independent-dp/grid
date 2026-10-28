"""Helpers for GRID regression tests.

Compilation and public solve are deliberately exercised separately.  Tests
are tiny and have known expected solutions; never assert elapsed times.
"""

import didppy as dp
from grid.didp_converter import DIDPConverter


def compile_model(routing_model):
    converter = DIDPConverter(routing_model)
    compiled = converter.get_didp_model()
    assert isinstance(compiled, dp.Model)
    return converter


def solve_compiled(routing_model, time_limit=20):
    converter = compile_model(routing_model)
    # RoutingModel.solve is the documented public entry point.
    result = routing_model.solve(solver="CABS", time_limit=time_limit)
    assert isinstance(result, dict)
    return converter, result


def served_customers(result):
    """Flatten the reported single-depot routes into a visit sequence."""
    routes = result.get("Solution") or []
    return [node for route in routes for node in route]
