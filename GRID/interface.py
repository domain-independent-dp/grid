from __future__ import annotations
import networkx as nx
from typing import Literal
from .expressions import *
from .didp_converter import DIDPConverter
from sys import intern

class VarCounter:

    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1

class Transition:

    def __init__(self, var, expression, need_uid = True):
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
            return intern(f"{expr.op}"+self._generate_uid(expr.left))
        return intern(self._generate_uid(expr.left) +  f"{expr.op}" + self._generate_uid(expr.right))
    
    def __eq__(self, other):
        return self.uid is other.uid and self.var.id == other.var.id and self.numeric_type == other.numeric_type
    
class Constraint:

    def __init__(self, expression, need_uid = True):
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
            return intern(f"{expr.op}"+self._generate_uid(expr.left))
        return intern(self._generate_uid(expr.left) +  f"{expr.op}" + self._generate_uid(expr.right))
    
    def __eq__(self, other):
        return self.uid is other.uid and self.numeric_type == other.numeric_type


class Node:

    def __init__(self,
                 id: int,
                 demand: dict[str,float]| int | float = None,
                 tw_start: float=None,
                 tw_end: float=None,
                 service_t: float=None,
                 waiting_t: float=None,
                 pickup: dict[str, float] = {},
                 delivery: dict[str, float] = {},
                 max_pickup_waiting: dict[str, float] = None,
                 max_ride_time: dict[str, float] = None,
                 precedence: list[int]=[],
                 profit: float=None,
                 optional: bool=False,
                 max_visits: int=1,
                 depot: bool=False):
        self.id = id
        self.demand = demand
        self.tw_start = tw_start
        self.tw_end = tw_end
        self.service_t = service_t
        self.waiting_t = waiting_t
        self.pickup = pickup
        self.delivery = delivery
        self.max_pickup_waiting = max_pickup_waiting
        self.max_ride_time = max_ride_time
        self.precedence = precedence
        self.profit=profit
        self.optional=optional
        self.max_visits = max_visits
        self.depot = depot
        self.transitions: list[Transition] = []
        self.constraints: list[Constraint] = []
    
    def add_transition(self,
                       var: Var,
                       expression):
        self.transitions.append(Transition(var, Expr._to_expr(expression), False))

    def add_constraint(self,
                       constraint):
        self.constraints.append(Constraint(Expr._to_expr(constraint), False))


class VehicleType:

    def __init__(self,
                 id: int,
                 var_counter: VarCounter,
                 count: int=1,
                 capacity: dict[str,float]| int | float = None,
                 max_distance: float=None,
                 max_nodes: int=None,
                 max_time: float=None,
                 max_cost: float=None,
                 min_profit: float=None,
                 start_node: int=None,
                 end_node: int=None,
                 fixed_cost: float=None):
        self.id = id
        self.var_counter = var_counter
        self.count = count
        self.capacity = capacity
        self.max_distance = max_distance
        self.max_nodes = max_nodes
        self.max_time = max_time
        self.max_cost = max_cost
        self.min_profit = min_profit
        self.start_node = start_node
        self.end_node = end_node
        self.fixed_cost = fixed_cost
        self.variables: list[Var] = []

    def add_integer_var(self,
                     initial_value: int,
                     preference: Literal["low", "high", None]=None)->Var:
        var = Var(self.var_counter.value, "integer", initial_value=initial_value, preference=preference)
        self.variables.append(var)
        self.var_counter.increment()
        return var
    
    def add_float_var(self,
                     initial_value: float,
                     preference: Literal["low", "high", None]=None)->Var:
        var = Var(self.var_counter.value, "float", initial_value=initial_value, preference=preference)
        self.variables.append(var)
        self.var_counter.increment()
        return var
    
    def add_nodes_set_var(self, 
                          initial_value: set | list):
        set_var = SetVar(self.var_counter.value, initial_value=initial_value)
        self.variables.append(set_var)
        self.var_counter.increment()
        return set_var


class Edge:

    def __init__(self,
                 node_from: Node,
                 node_to: Node,
                 distance: float=None,
                 travel_time: float=None,
                 variable_cost: dict[int, float]=None):
        self.node_from = node_from
        self.node_to = node_to
        self.distance = distance
        self.travel_time = travel_time
        self.variable_cost = variable_cost
        self.transitions: list[Transition] = []
        self.constraints: list[Constraint] = []
    
    def add_transition(self,
                       var: Var,
                       expression):
        self.transitions.append(Transition(var, Expr._to_expr(expression)))

    def add_constraint(self,
                       constraint):
        self.constraints.append(Constraint(Expr._to_expr(constraint)))

     
class RoutingModel:

    def __init__(self,
                 triangular_inequality:bool = True):
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
        self.var_counter = VarCounter()

    def add_node(self,
                 id: int,
                 demand: dict[str,float]| int | float = None,
                 tw_start: float=None,
                 tw_end: float=None,
                 service_t: float=None,
                 waiting_t: float=None,
                 pickup: dict[str, float]=None,
                 delivery: dict[str, float]=None,
                 max_pickup_waiting: dict[str, float] = None,
                 max_ride_time: dict[str, float] = None,
                 precedence: list[int]=None,
                 profit: float=None,
                 optional: bool=False,
                 max_visits:int = 1,
                 depot: bool=False)->Node:
        node = Node(id=id,
                    demand=demand,
                    tw_start=tw_start,
                    tw_end=tw_end,
                    service_t=service_t,
                    waiting_t=waiting_t,
                    pickup=pickup,
                    delivery=delivery,
                    precedence=precedence,
                    max_pickup_waiting=max_pickup_waiting,
                    max_ride_time=max_ride_time,
                    profit=profit,
                    optional=optional,
                    max_visits=max_visits,
                    depot=depot)
        self.graph.add_node(id, 
                            data=node)
        if depot:
            self.depots += 1
        return node
        
    def add_edge(self,
                 node_from: Node,
                 node_to: Node,
                 distance: float=None,
                 travel_time: float=None,
                 variable_cost:  dict[int, float]=None)->Edge:
        edge = Edge(node_from=node_from,
                    node_to=node_to,
                    distance=distance,
                    travel_time=travel_time,
                    variable_cost = variable_cost)
        self.graph.add_edge(node_from.id, 
                            node_to.id, 
                            edge=edge)
        return edge
        
    def add_vehicle_type(self,
                    id: int,
                    count: int=1,
                    capacity: dict[str,float]| int | float = None,
                    max_distance: float=None,
                    max_nodes: int=None,
                    max_time: float=None,
                    max_cost: float=None,
                    min_profit: float=None,
                    start_node: int=None,
                    end_node: int=None,
                    fixed_cost: float=None)->VehicleType:
        vehicle = VehicleType(id=id,
                          var_counter=self.var_counter,
                          count=count,
                          capacity=capacity,
                          max_distance=max_distance,
                          max_nodes=max_nodes,
                          max_time=max_time,
                          max_cost=max_cost,
                          min_profit=min_profit,
                          start_node=start_node,
                          end_node=end_node,
                          fixed_cost=fixed_cost)
        self.vehicles[id] = vehicle
        self.vehicles_count += count
        self.vehicle_types += 1
        return vehicle
        
    def get_node(self, id:int)->Node:
        return self.graph.nodes[id]["data"]
    
    def get_nodes(self)->list[Node]:
        node_tuples = self.graph.nodes(data=True)
        node_tuples = sorted(node_tuples, key = lambda x:x[0])
        return [node[1]["data"] for node in node_tuples]
    
    def get_vehicle_types(self)->list[VehicleType]:
        vehicles = self.vehicles.values()
        return sorted(vehicles, key= lambda x:x.id)
    
    def get_vehicle_type(self, id:int)->VehicleType:
        return self.vehicles[id]
    
    def get_edge(self,
                 node_from: int,
                 node_to: int)->Edge:
        data = self.graph.get_edge_data(node_from, node_to)
        return data["edge"] if data else None
    
    def get_edges(self)->list[Edge]:
        edge_tuples = self.graph.edges(data=True)
        edge_tuples = sorted(edge_tuples, key= lambda x:(x[0], x[1]))
        return [edge[2]["edge"] for edge in edge_tuples]

    def add_constraint(self,
                       constraint):
        self.constraints.append(Constraint(Expr._to_expr(constraint), False))

    def add_integer_var(self,
                     initial_value: int,
                     preference: Literal["low", "high", None]=None)->Var:
        var = Var(self.var_counter.value, var_type="integer", initial_value=initial_value, preference=preference)
        self.variables.append(var)
        self.var_counter.increment()
        return var
    
    def add_float_var(self,
                     initial_value: float,
                     preference: Literal["low", "high", None]=None)->Var:
        var = Var(self.var_counter.value, var_type="float", initial_value=initial_value, preference=preference)
        self.variables.append(var)
        self.var_counter.increment()
        return var
    
    def add_nodes_set_var(self, 
                          initial_value: set | list):
        set_var = SetVar(self.var_counter.value, initial_value=initial_value)
        self.variables.append(set_var)
        self.var_counter.increment()
        return set_var
    
    def add_shortest_distance(self,
                              shortest_distance)->None:
        self.shortest_distance = shortest_distance

    def add_shortest_time(self,
                          shortest_time)->None:
        self.shortest_time = shortest_time

    def set_objective(self,
                 metric: Literal["distance", "time", "num_vehicles"] = None,
                 variables: Var | list[Var] = None,
                 aggregation: Literal["max", "sum"] = "sum",
                 maximize: bool = False):
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

    def solve(self, solver: Literal["LNBS", "CABS"] = "LNBS", time_limit:float=None):
        converter = DIDPConverter(self, self.maximize)
        return converter.solve(solver, time_limit)