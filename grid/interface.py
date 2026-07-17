"""User-facing modelling interface for GRID.

This module defines the public objects users interact with to build a Vehicle
Routing Problem instance: :class:`RoutingModel` (the model), :class:`Node`,
:class:`Edge`, :class:`VehicleType`, and the :class:`Transition` /
:class:`Constraint` building blocks attached to nodes and edges.
"""

from __future__ import annotations

from sys import intern
from typing import Literal

import networkx as nx

from .didp_converter import DIDPConverter
from .expressions import Const, Expr, SetVar, Var


class _VarCounter:
    """Monotonic counter used to assign unique ids to decision variables."""

    def __init__(self):
        self.value = 0

    def increment(self):
        """Increment the counter by one."""
        self.value += 1


class Transition:
    """Effect of taking a transition: assignment of an expression to a variable.

    Transitions are attached to :class:`Node` and :class:`Edge` objects via
    :meth:`Node.add_transition` and :meth:`Edge.add_transition`. A unique id
    (``uid``) is generated from the structure of the right-hand side expression
    and used to deduplicate equivalent transitions across the model.

    Parameters
    ----------
    var : Var
        The decision variable being updated.
    expression : Expr
        The expression assigned to ``var`` when the transition is taken.
    need_uid : bool, default: True
        Whether to compute and store a unique id from the expression structure.
        Set to ``False`` to skip uid generation when deduplication is not needed.

    Attributes
    ----------
    var : Var
        The decision variable being updated.
    expression : Expr
        The right-hand side expression.
    numeric_type : {"integer", "float"}
        Numeric type inferred from the expression.
    uid : str or None
        Interned string identifying the expression structure, or ``None`` if
        ``need_uid=False`` was passed.
    """

    def __init__(self, var, expression, need_uid=True):
        self.var = var
        self.expression = expression
        self.numeric_type = expression.type
        if need_uid:
            self.uid = self._generate_uid(expression)
        else:
            self.uid = None

    def _generate_uid(self, expr):
        if isinstance(expr, Var):
            if self.var.id == expr.id:
                return intern("Var")
            else:
                return intern(str(Var))
        if isinstance(expr, Const):
            return intern("Const")
        if expr.right is None:
            return intern(f"{expr.op}" + self._generate_uid(expr.left))
        return intern(self._generate_uid(expr.left) + f"{expr.op}" + self._generate_uid(expr.right))

    def __eq__(self, other):
        return (
            self.uid is other.uid
            and self.var.id == other.var.id
            and self.numeric_type == other.numeric_type
        )


class Constraint:
    """Boolean condition that must hold for a transition to be applicable.

    Constraints are attached to :class:`Node`, :class:`Edge`, or :class:`RoutingModel`
    via their respective ``add_constraint`` methods. A unique id (``uid``) is
    generated from the structure of the expression and used to deduplicate
    equivalent constraints across the model.

    Parameters
    ----------
    expression : Expr
        Boolean expression representing the constraint.
    need_uid : bool, default: True
        Whether to compute and store a unique id from the expression structure.

    Attributes
    ----------
    expression : Expr
        The constraint expression.
    numeric_type : {"integer", "float"}
        Numeric type of the expression (``"float"`` if any sub-expression is float,
        ``"integer"`` otherwise).
    uid : str or None
        Interned string identifying the expression structure, or ``None`` if
        ``need_uid=False`` was passed.
    """

    def __init__(self, expression, need_uid=True):
        self.expression = expression
        self.numeric_type = "integer"
        if need_uid:
            self.uid = self._generate_uid(expression)
        else:
            self.uid = None

    def _generate_uid(self, expr):
        if expr.type == "float":
            self.numeric_type = "float"
        if isinstance(expr, Var):
            return intern(str(expr))
        if isinstance(expr, Const):
            return intern("Const")
        if expr.right is None:
            return intern(f"{expr.op}" + self._generate_uid(expr.left))
        return intern(self._generate_uid(expr.left) + f"{expr.op}" + self._generate_uid(expr.right))

    def __eq__(self, other):
        return self.uid is other.uid and self.numeric_type == other.numeric_type


class Node:
    """Vertex of the routing graph, representing a customer, depot, or stop.

    Holds attributes used to model many VRP variants: demand (CVRP), time windows
    (VRPTW), pickup/delivery quantities (PDPTW), precedence, optional visits and
    profits (orienteering / TOP), and depot flags.

    Parameters
    ----------
    id : int
        Unique identifier of the node within the model.
    demand : dict of str to float, int, or float, optional
        Demand consumed when visiting the node. A scalar value is treated as
        single-commodity demand; a dict maps commodity name to per-commodity
        demand for multi-commodity problems.
    tw_start : float, optional
        Earliest time at which service can begin at the node.
    tw_end : float, optional
        Latest time at which service can begin at the node.
    service_t : float, optional
        Service time required at the node.
    waiting_t : float, optional
        Maximum waiting time allowed at the node before its time window opens.
        Caps how long a vehicle may wait when it arrives before ``tw_start``.
    pickup : dict of str to float, default: {}
        Quantities picked up at the node, mapped by commodity name (PDPTW).
    delivery : dict of str to float, default: {}
        Quantities delivered at the node, mapped by commodity name (PDPTW).
    optional : bool, default: False
        Whether the node may be skipped.
    max_visits : int, default: 1
        Maximum number of times the node may be visited.
    depot : bool, default: False
        Whether the node acts as a depot.

    Attributes
    ----------
    transitions : list of Transition
        Transitions registered on this node via :meth:`add_transition`.
    constraints : list of Constraint
        Constraints registered on this node via :meth:`add_constraint`.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> depot = model.add_node(id=0, depot=True)
    >>> customer = model.add_node(id=1, demand=3, service_t=2)
    >>> customer.demand
    3
    >>> depot.depot
    True
    """

    def __init__(
        self,
        id: int,
        demand: dict[str, float] | int | float = None,
        tw_start: float = None,
        tw_end: float = None,
        service_t: float = None,
        waiting_t: float = None,
        pickup: dict[str, float] = None,
        delivery: dict[str, float] = None,
        #max_pickup_waiting: dict[str, float] = None,       not yet implemented
        #max_ride_time: dict[str, float] = None,            not yet implemented
        #precedence: list[int] = None,                      not yet implemented
        #profit: float = None,                              not yet implemented
        optional: bool = False,
        max_visits: int = 1,
        depot: bool = False,
    ):
        self.id = id
        self.demand = demand
        self.tw_start = tw_start
        self.tw_end = tw_end
        self.service_t = service_t
        self.waiting_t = waiting_t
        self.pickup = pickup if pickup is not None else {}
        self.delivery = delivery if delivery is not None else {}
        #self.max_pickup_waiting = max_pickup_waiting                           not yet implemented
        #self.max_ride_time = max_ride_time                                     not yet implemented
        #self.precedence = precedence if precedence is not None else []         not yet implemented
        #self.profit = profit                                                   not yet implemented
        self.optional = optional
        self.max_visits = max_visits
        self.depot = depot
        self.transitions: list[Transition] = []
        self.constraints: list[Constraint] = []

    def add_transition(self, var: Var, expression):
        """Register a variable update applied when the node is visited.

        Parameters
        ----------
        var : Var
            The decision variable to update.
        expression : Expr or int or float or bool
            Expression assigned to ``var``. Python literals are automatically wrapped
            into a :class:`Const`.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> customer = model.add_node(id=1, demand=3)
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> load = vehicle.add_integer_var(initial_value=10)
        >>> customer.add_transition(var=load, expression=load - 3)
        >>> len(customer.transitions)
        1
        """
        self.transitions.append(Transition(var, Expr._to_expr(expression), False))

    def add_constraint(self, constraint):
        """Register a boolean precondition required to visit this node.

        Parameters
        ----------
        constraint : Expr
            Boolean expression that must evaluate to true for the node to be visited.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> customer = model.add_node(id=1, demand=3)
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> load = vehicle.add_integer_var(initial_value=10)
        >>> customer.add_constraint(load - 3 >= 0)
        >>> len(customer.constraints)
        1
        """
        self.constraints.append(Constraint(Expr._to_expr(constraint), False))


class VehicleType:
    """Definition of a homogeneous group of vehicles sharing the same parameters.

    A model may contain several vehicle types, each with its own count,
    capacity, permitted depots, and user-defined variables.

    Parameters
    ----------
    id : int
        Unique identifier of the vehicle type.
    count : int, default: 1
        Number of vehicles of this type available.
    capacity : dict of str to float, int, or float, optional
        Vehicle capacity. Scalar for single-commodity, dict mapping commodity name
        to per-commodity capacity for multi-commodity problems.
    start_node : int, optional
        Id of the node where vehicles of this type start.
    end_node : int, optional
        Id of the node where vehicles of this type must end.

    Attributes
    ----------
    variables : list of Var
        Decision variables registered on this vehicle type via
        :meth:`add_integer_var`, :meth:`add_float_var`, :meth:`add_nodes_set_var`.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=2, capacity=10)
    >>> vehicle.count
    2
    >>> load = vehicle.add_integer_var(initial_value=10)
    >>> load
    Var_0
    """

    def __init__(
        self,
        id: int,
        count: int = 1,
        capacity: dict[str, float] | int | float = None,
        #max_distance: float = None,                        not yet implemented
        #max_nodes: int = None,                             not yet implemented
        #max_time: float = None,                            not yet implemented
        #max_cost: float = None,                            not yet implemented
        #min_profit: float = None,                          not yet implemented
        start_node: int = None,
        end_node: int = None,
        #fixed_cost: float = None,                          not yet implemented
    ):
        self.id = id
        self.var_counter = None                             #injected by RoutingModel.add_vehicle_type
        self.count = count
        self.capacity = capacity
        #self.max_distance = max_distance                   not yet implemented
        #self.max_nodes = max_nodes                         not yet implemented
        #self.max_time = max_time                           not yet implemented
        #self.max_cost = max_cost                           not yet implemented
        #self.min_profit = min_profit                       not yet implemented
        self.start_node = start_node
        self.end_node = end_node
        #self.fixed_cost = fixed_cost                       not yet implemented
        self.variables: list[Var] = []

    def add_integer_var(
        self, initial_value: int, preference: Literal["low", "high", None] = None
    ) -> Var:
        """Create an integer decision variable bound to this vehicle type.

        Parameters
        ----------
        initial_value : int
            Initial value of the variable at the start of the route.
        preference : {"low", "high", None}, default: None
            Solver hint indicating whether smaller or larger values should be
            preferred. ``None`` leaves the search neutral.

        Returns
        -------
        Var
            The newly created variable.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> load = vehicle.add_integer_var(initial_value=10)
        >>> load.initial_value
        10
        >>> load.type
        'integer'
        """
        var = Var(
            self.var_counter.value, "integer", initial_value=initial_value, preference=preference
        )
        self.variables.append(var)
        self.var_counter.increment()
        return var

    def add_float_var(
        self, initial_value: float, preference: Literal["low", "high", None] = None
    ) -> Var:
        """Create a float decision variable bound to this vehicle type.

        Parameters
        ----------
        initial_value : float
            Initial value of the variable at the start of the route.
        preference : {"low", "high", None}, default: None
            Solver hint indicating whether smaller or larger values should be
            preferred. ``None`` leaves the search neutral.

        Returns
        -------
        Var
            The newly created variable.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> battery = vehicle.add_float_var(initial_value=100.0, preference="high")
        >>> battery.preference
        'high'
        >>> battery.type
        'float'
        """
        var = Var(
            self.var_counter.value, "float", initial_value=initial_value, preference=preference
        )
        self.variables.append(var)
        self.var_counter.increment()
        return var

    def add_nodes_set_var(self, initial_value: set | list):
        """Create a set decision variable bound to this vehicle type.

        Used to track sets of node ids over the route (e.g. unvisited or visited
        nodes).

        Parameters
        ----------
        initial_value : set or list
            Initial contents of the set at the start of the route.

        Returns
        -------
        SetVar
            The newly created set variable.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
        >>> sorted(stations.initial_value)
        [3, 4]
        """
        set_var = SetVar(self.var_counter.value, initial_value=initial_value)
        self.variables.append(set_var)
        self.var_counter.increment()
        return set_var


class Edge:
    """Directed arc of the routing graph between two :class:`Node` instances.

    Holds attributes used to model travel distance and time between nodes.

    Parameters
    ----------
    node_from : Node
        Source node of the edge.
    node_to : Node
        Destination node of the edge.
    distance : float, optional
        Travel distance along the edge.
    travel_time : float, optional
        Travel time along the edge.

    Attributes
    ----------
    transitions : list of Transition
        Transitions registered on this edge via :meth:`add_transition`.
    constraints : list of Constraint
        Constraints registered on this edge via :meth:`add_constraint`.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> a = model.add_node(id=0, depot=True)
    >>> b = model.add_node(id=1, demand=3)
    >>> edge = model.add_edge(node_from=a, node_to=b, distance=4)
    >>> edge.distance
    4
    """

    def __init__(
        self,
        node_from: Node,
        node_to: Node,
        distance: float = None,
        travel_time: float = None,
        #variable_cost: dict[int, float] = None,    not yet implemented
    ):
        self.node_from = node_from
        self.node_to = node_to
        self.distance = distance
        self.travel_time = travel_time
        #self.variable_cost = variable_cost         not yet implemented
        self.transitions: list[Transition] = []
        self.constraints: list[Constraint] = []

    def add_transition(self, var: Var, expression):
        """Register a variable update applied when the edge is traversed.

        Parameters
        ----------
        var : Var
            The decision variable to update.
        expression : Expr or int or float or bool
            Expression assigned to ``var``. Python literals are automatically wrapped
            into a :class:`Const`.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> a = model.add_node(id=0, depot=True)
        >>> b = model.add_node(id=1, demand=3)
        >>> edge = model.add_edge(node_from=a, node_to=b, distance=4)
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> battery = vehicle.add_float_var(initial_value=100.0, preference="high")
        >>> edge.add_transition(var=battery, expression=battery - 4)
        >>> len(edge.transitions)
        1
        """
        self.transitions.append(Transition(var, Expr._to_expr(expression)))

    def add_constraint(self, constraint):
        """Register a boolean precondition required to traverse this edge.

        Parameters
        ----------
        constraint : Expr
            Boolean expression that must evaluate to true for the edge to be traversed.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> a = model.add_node(id=0, depot=True)
        >>> b = model.add_node(id=1, demand=3)
        >>> edge = model.add_edge(node_from=a, node_to=b, distance=4)
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> battery = vehicle.add_float_var(initial_value=100.0, preference="high")
        >>> edge.add_constraint(battery - 4 >= 0)
        >>> len(edge.constraints)
        1
        """
        self.constraints.append(Constraint(Expr._to_expr(constraint)))


class RoutingModel:
    """High-level model of a Vehicle Routing Problem.

    A ``RoutingModel`` represents a routing problem as a directed graph of
    :class:`Node` and :class:`Edge` objects together with one or more
    :class:`VehicleType` definitions, decision variables, constraints, and an
    objective. Once configured, the model is compiled to a DIDP model and solved
    by calling :meth:`solve`.

    The class supports several VRP variants
    depending on which optional attributes are set on the nodes, edges, and
    vehicle types.

    Parameters
    ----------
    triangular_inequality : bool, default: True
        Whether the underlying distance and time data satisfy the triangular
        inequality.

    Attributes
    ----------
    graph : networkx.DiGraph
        Directed graph holding :class:`Node` data on vertices and :class:`Edge`
        data on arcs.
    vehicles : dict of int to VehicleType
        Vehicle types registered on the model, indexed by id.
    constraints : list of Constraint
        Global constraints registered on the model.
    variables : list of Var
        Global decision variables registered on the model.
    objective : Expr or {"total_distance", "total_vehicles"} or None
        The configured objective expression, or ``None`` until
        :meth:`set_objective` is called.
    depots : int
        Number of nodes flagged as depots.
    vehicles_count : int
        Total number of vehicles across all registered types.
    vehicle_types : int
        Number of registered :class:`VehicleType` instances.
    shortest_distance : optional
        Precomputed shortest-distance data, set via :meth:`add_shortest_distance`.
    shortest_time : optional
        Precomputed shortest-time data, set via :meth:`add_shortest_time`.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> depot = model.add_node(id=0, depot=True)
    >>> a = model.add_node(id=1, demand=3)
    >>> b = model.add_node(id=2, demand=5)
    >>> distances = {(0, 1): 4, (1, 0): 4, (0, 2): 6, (2, 0): 6, (1, 2): 3, (2, 1): 3}
    >>> for (i, j), d in distances.items():
    ...     _ = model.add_edge(node_from=model.get_node(i), node_to=model.get_node(j), distance=d)
    >>> vehicle = model.add_vehicle_type(id=0, count=2, capacity=10)
    >>> model.set_objective(metric="distance")
    >>> result = model.solve(solver="CABS", time_limit=10)
    >>> result["Optimal"]
    True
    >>> result["Cost"]
    13
    """

    def __init__(self, triangular_inequality: bool = True):
        self.triangular_inequality = triangular_inequality
        self.graph = nx.DiGraph()
        self.vehicles: dict[int, VehicleType] = {}
        self.constraints: list[Constraint] = []
        self.variables: list[Var] = []
        self.objective: Expr | Literal["total_distance", "total_vehicles"] = None
        self.depots: int = 0
        self.vehicles_count: int = 0
        self.vehicle_types: int = 0
        self.operator = None
        self.shortest_distance = None
        self.shortest_time = None
        self.var_counter = _VarCounter()

    def add_node(
        self,
        id: int,
        demand: dict[str, float] | int | float = None,
        tw_start: float = None,
        tw_end: float = None,
        service_t: float = None,
        waiting_t: float = None,
        pickup: dict[str, float] = None,
        delivery: dict[str, float] = None,
        #max_pickup_waiting: dict[str, float] = None,       not yet implemented
        #max_ride_time: dict[str, float] = None,            not yet implemented
        #precedence: list[int] = None,                      not yet implemented
        #profit: float = None,                              not yet implemented
        optional: bool = False,
        max_visits: int = 1,
        depot: bool = False,
    ) -> Node:
        """Add a node to the routing graph.

        Parameters
        ----------
        id : int
            Unique identifier of the node.
        demand : dict of str to float, int, or float, optional
            Demand consumed when visiting the node.
        tw_start : float, optional
            Earliest time at which service can begin.
        tw_end : float, optional
            Latest time at which service can begin.
        service_t : float, optional
            Service time required at the node.
        waiting_t : float, optional
            Maximum waiting time allowed before the time window opens.
        pickup : dict of str to float, optional
            Quantities picked up at the node, per commodity.
        delivery : dict of str to float, optional
            Quantities delivered at the node, per commodity.
        optional : bool, default: False
            Whether the node may be skipped.
        max_visits : int, default: 1
            Maximum number of times the node may be visited.
        depot : bool, default: False
            Whether the node acts as a depot.

        Returns
        -------
        Node
            The newly created node, also retrievable via :meth:`get_node`.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> depot = model.add_node(id=0, depot=True)
        >>> customer = model.add_node(id=1, demand=3, tw_start=0, tw_end=10)
        >>> customer.demand
        3
        >>> customer.optional
        False
        """
        node = Node(
            id=id,
            demand=demand,
            tw_start=tw_start,
            tw_end=tw_end,
            service_t=service_t,
            waiting_t=waiting_t,
            pickup=pickup,
            delivery=delivery,
            #precedence=precedence,                         not yet implemented
            #max_pickup_waiting=max_pickup_waiting,         not yet implemented
            #max_ride_time=max_ride_time,                   not yet implemented
            #profit=profit,                                 not yet implemented
            optional=optional,
            max_visits=max_visits,
            depot=depot,
        )
        self.graph.add_node(id, data=node)
        if depot:
            self.depots += 1
        return node

    def add_edge(
        self,
        node_from: Node,
        node_to: Node,
        distance: float = None,
        travel_time: float = None,
        #variable_cost: dict[int, float] = None,                            not yet implemented
    ) -> Edge:
        """Add a directed edge between two nodes of the routing graph.

        Parameters
        ----------
        node_from : Node
            Source node.
        node_to : Node
            Destination node.
        distance : float, optional
            Travel distance along the edge.
        travel_time : float, optional
            Travel time along the edge.

        Returns
        -------
        Edge
            The newly created edge, also retrievable via :meth:`get_edge`.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> a = model.add_node(id=0, depot=True)
        >>> b = model.add_node(id=1, demand=3)
        >>> edge = model.add_edge(node_from=a, node_to=b, distance=4, travel_time=6)
        >>> edge.distance
        4
        >>> edge.travel_time
        6
        """
        edge = Edge(
            node_from=node_from,
            node_to=node_to,
            distance=distance,
            travel_time=travel_time,
            #variable_cost=variable_cost,                                   not yet implemented
        )
        self.graph.add_edge(node_from.id, node_to.id, edge=edge)
        return edge

    def add_vehicle_type(
        self,
        id: int,
        count: int = 1,
        capacity: dict[str, float] | int | float = None,
        #max_distance: float = None,                            not yet implemented
        #max_nodes: int = None,                                 not yet implemented
        #max_time: float = None,                                not yet implemented
        #max_cost: float = None,                                not yet implemented
        #min_profit: float = None,                              not yet implemented
        start_node: int = None,
        end_node: int = None,
        #fixed_cost: float = None,                              not yet implemented
    ) -> VehicleType:
        """Register a new vehicle type on the model.

        Parameters
        ----------
        id : int
            Unique identifier of the vehicle type.
        count : int, default: 1
            Number of vehicles of this type available.
        capacity : dict of str to float, int, or float, optional
            Vehicle capacity (per commodity if dict, scalar otherwise).
        start_node : int, optional
            Id of the start node for vehicles of this type.
        end_node : int, optional
            Id of the end node for vehicles of this type.

        Returns
        -------
        VehicleType
            The newly created vehicle type, also retrievable via
            :meth:`get_vehicle_type`.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=3, capacity=15)
        >>> vehicle.count
        3
        >>> vehicle.capacity
        15
        """
        vehicle = VehicleType(
            id=id,
            count=count,
            capacity=capacity,
            #max_distance=max_distance,
            #max_nodes=max_nodes,
            #max_time=max_time,
            #max_cost=max_cost,
            #min_profit=min_profit,
            start_node=start_node,
            end_node=end_node,
            #fixed_cost=fixed_cost,
        )
        vehicle.var_counter = self.var_counter
        self.vehicles[id] = vehicle
        self.vehicles_count += count
        self.vehicle_types += 1
        return vehicle

    def get_node(self, id: int) -> Node:
        """Return the :class:`Node` with the given id.

        Parameters
        ----------
        id : int
            Node identifier.

        Returns
        -------
        Node

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> depot = model.add_node(id=0, depot=True)
        >>> model.get_node(0) is depot
        True
        """
        return self.graph.nodes[id]["data"]

    def get_nodes(self) -> list[Node]:
        """Return all nodes of the model, sorted by id.

        Returns
        -------
        list of Node

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> _ = model.add_node(id=0, depot=True)
        >>> _ = model.add_node(id=1, demand=3)
        >>> len(model.get_nodes())
        2
        """
        node_tuples = self.graph.nodes(data=True)
        node_tuples = sorted(node_tuples, key=lambda x: x[0])
        return [node[1]["data"] for node in node_tuples]

    def get_vehicle_types(self) -> list[VehicleType]:
        """Return all registered vehicle types, sorted by id.

        Returns
        -------
        list of VehicleType

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> _ = model.add_vehicle_type(id=0, count=2, capacity=10)
        >>> _ = model.add_vehicle_type(id=1, count=1, capacity=20)
        >>> len(model.get_vehicle_types())
        2
        """
        vehicles = self.vehicles.values()
        return sorted(vehicles, key=lambda x: x.id)

    def get_vehicle_type(self, id: int) -> VehicleType:
        """Return the :class:`VehicleType` with the given id.

        Parameters
        ----------
        id : int
            Vehicle type identifier.

        Returns
        -------
        VehicleType

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=2, capacity=10)
        >>> model.get_vehicle_type(0) is vehicle
        True
        """
        return self.vehicles[id]

    def get_edge(self, node_from: int, node_to: int) -> Edge:
        """Return the :class:`Edge` connecting two nodes, if any.

        Parameters
        ----------
        node_from : int
            Id of the source node.
        node_to : int
            Id of the destination node.

        Returns
        -------
        Edge or None
            The edge if one exists between ``node_from`` and ``node_to``, otherwise
            ``None``.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> a = model.add_node(id=0, depot=True)
        >>> b = model.add_node(id=1, demand=3)
        >>> _ = model.add_edge(node_from=a, node_to=b, distance=4)
        >>> model.get_edge(0, 1).distance
        4
        """
        data = self.graph.get_edge_data(node_from, node_to)
        return data["edge"] if data else None

    def get_edges(self) -> list[Edge]:
        """Return all edges of the model, sorted by ``(node_from, node_to)``.

        Returns
        -------
        list of Edge

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> a = model.add_node(id=0, depot=True)
        >>> b = model.add_node(id=1, demand=3)
        >>> _ = model.add_edge(node_from=a, node_to=b, distance=4)
        >>> _ = model.add_edge(node_from=b, node_to=a, distance=4)
        >>> len(model.get_edges())
        2
        """
        edge_tuples = self.graph.edges(data=True)
        edge_tuples = sorted(edge_tuples, key=lambda x: (x[0], x[1]))
        return [edge[2]["edge"] for edge in edge_tuples]

    def add_constraint(self, constraint):
        """Register a global constraint on the model.

        Parameters
        ----------
        constraint : Expr
            Boolean expression that must hold throughout the route.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> load = vehicle.add_integer_var(initial_value=10)
        >>> model.add_constraint(load >= 0)
        >>> len(model.constraints)
        1
        """
        self.constraints.append(Constraint(Expr._to_expr(constraint), False))

    def add_integer_var(
        self, initial_value: int, preference: Literal["low", "high", None] = None
    ) -> Var:
        """Create a global integer decision variable on the model.

        Parameters
        ----------
        initial_value : int
            Initial value of the variable.
        preference : {"low", "high", None}, default: None
            Solver hint indicating preferred direction.

        Returns
        -------
        Var

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> counter = model.add_integer_var(initial_value=0, preference="low")
        >>> counter
        Var_0
        >>> counter.initial_value
        0
        """
        var = Var(
            self.var_counter.value,
            var_type="integer",
            initial_value=initial_value,
            preference=preference,
        )
        self.variables.append(var)
        self.var_counter.increment()
        return var

    def add_float_var(
        self, initial_value: float, preference: Literal["low", "high", None] = None
    ) -> Var:
        """Create a global float decision variable on the model.

        Parameters
        ----------
        initial_value : float
            Initial value of the variable.
        preference : {"low", "high", None}, default: None
            Solver hint indicating preferred direction.

        Returns
        -------
        Var

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> level = model.add_float_var(initial_value=1.5)
        >>> level.initial_value
        1.5
        >>> level.type
        'float'
        """
        var = Var(
            self.var_counter.value,
            var_type="float",
            initial_value=initial_value,
            preference=preference,
        )
        self.variables.append(var)
        self.var_counter.increment()
        return var

    def add_nodes_set_var(self, initial_value: set | list):
        """Create a global set decision variable on the model.

        Parameters
        ----------
        initial_value : set or list
            Initial contents of the set.

        Returns
        -------
        SetVar

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> visited = model.add_nodes_set_var(initial_value={1, 2, 3})
        >>> visited
        SetVar_0
        >>> sorted(visited.initial_value)
        [1, 2, 3]
        """
        set_var = SetVar(self.var_counter.value, initial_value=initial_value)
        self.variables.append(set_var)
        self.var_counter.increment()
        return set_var

    def add_shortest_distance(self, shortest_distance) -> None:
        """Attach precomputed shortest-distance data to the model.

        Used by the converter to tighten dual bounds during solving.

        Parameters
        ----------
        shortest_distance
            Pre-computed shortest-distance matrix where entry ``[i][j]`` is the
            minimum distance from node ``i`` to node ``j``.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> matrix = [[0, 4], [4, 0]]
        >>> model.add_shortest_distance(matrix)
        >>> model.shortest_distance
        [[0, 4], [4, 0]]
        """
        self.shortest_distance = shortest_distance

    def add_shortest_time(self, shortest_time) -> None:
        """Attach precomputed shortest-time data to the model.

        Used by the converter to tighten dual bounds during solving.

        Parameters
        ----------
        shortest_time
            Pre-computed shortest-time matrix where entry ``[i][j]`` is the
            minimum travel time from node ``i`` to node ``j``.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> matrix = [[0, 6], [6, 0]]
        >>> model.add_shortest_time(matrix)
        >>> model.shortest_time
        [[0, 6], [6, 0]]
        """
        self.shortest_time = shortest_time

    def set_objective(
        self,
        metric: Literal["distance", "time", "num_vehicles"] = None,
        variables: Var | list[Var] = None,
        aggregation: Literal["max", "sum"] = "sum",
        maximize: bool = False,
    ):
        """Configure the objective of the model.

        Parameters
        ----------
        metric : {"distance", "time", "num_vehicles"}, optional
            Built-in objective metric to optimise.
        variables : Var or list of Var, optional
            Decision variables whose values participate in the objective when a
            custom aggregation over variables is desired.
        aggregation : {"max", "sum"}, default: "sum"
            Aggregation operator used to combine per-route or per-variable
            contributions.
        maximize : bool, default: False
            If ``True``, the objective is maximised; otherwise minimised.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> model.set_objective(metric="distance")
        >>> model.metric
        'distance'
        """
        self.metric = metric
        self.aggregation = aggregation
        self.objective_variables = variables
        self.maximize = maximize

    """
    def add_dual_bounds(self,
                       dual_bounds,
                       operator : Literal["plus", "product", "max", "min", "overwrite"]="plus"):
        self.dual_bounds = [dual_bounds] if not isinstance(dual_bounds, list) else dual_bounds
        self.operator = operator
    """

    def solve(self, solver: Literal["LNBS", "CABS"] = "LNBS", time_limit: float = None):
        """Compile the model to DIDP and solve it.

        Parameters
        ----------
        solver : {"LNBS", "CABS"}, default: "LNBS"
            DIDP anytime heuristic search algorithm to use.
        time_limit : float, optional
            Wall-clock time limit in seconds. ``None`` runs until completion or
            interruption.

        Returns
        -------
        dict
        Result of the search with the following keys:

        - ``"Optimal"`` (bool): whether the returned solution is proven optimal.
        - ``"Infeasible"`` (bool): whether the model was proven infeasible.
        - ``"Best Bound"`` (int or float): best dual bound found during search.
        - ``"Cost"`` (int, float, or None): cost of the best feasible solution found, or ``None`` if no feasible solution was found.
        - ``"Solution"`` (list or None): best route(s) found, or ``None`` if no feasible solution was found.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> depot = model.add_node(id=0, depot=True)
        >>> _ = model.add_node(id=1, demand=3)
        >>> _ = model.add_node(id=2, demand=5)
        >>> distances = {(0, 1): 4, (1, 0): 4, (0, 2): 6, (2, 0): 6, (1, 2): 3, (2, 1): 3}
        >>> for (i, j), d in distances.items():
        ...     _ = model.add_edge(node_from=model.get_node(i), node_to=model.get_node(j), distance=d)
        >>> _ = model.add_vehicle_type(id=0, count=2, capacity=10)
        >>> model.set_objective(metric="distance")
        >>> result = model.solve(solver="CABS", time_limit=10)
        >>> result["Optimal"]
        True
        >>> result["Cost"]
        13
        """
        converter = DIDPConverter(self, self.maximize)
        return converter.solve(solver, time_limit)
