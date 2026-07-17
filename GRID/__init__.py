"""GRID: Graph-based modelling Interface for Domain-Independent Dynamic Programming.

GRID provides a high-level, graph-based interface for modelling Vehicle Routing
Problem variants that compiles to DIDP models
and dispatches to DIDP solvers.

The typical workflow is:

1. Build a :class:`RoutingModel`.
2. Add :class:`Node` instances via :meth:`RoutingModel.add_node`.
3. Add :class:`Edge` instances via :meth:`RoutingModel.add_edge`.
4. Add :class:`VehicleType` instances via :meth:`RoutingModel.add_vehicle_type`.
5. Configure constraints, variables, and the objective on the model. Build
   expressions over :class:`Var` and :class:`SetVar` with native Python
   operators, or use :func:`max`, :func:`min`, :func:`sqrt`, :func:`log`,
   :func:`select` for operations that have no operator equivalent.
6. Call :meth:`RoutingModel.solve` to compile to DIDP and solve.
"""

from .expressions import SetVar, Var, log, max, min, select, sqrt
from .interface import Edge, Node, RoutingModel, VehicleType

__all__ = [
    "RoutingModel",
    "Node",
    "Edge",
    "VehicleType",
    "Var",
    "SetVar",
    "max",
    "min",
    "sqrt",
    "log",
    "select",
]

__version__ = "0.1.0"
