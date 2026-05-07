import didppy as dp
from .expressions_manager import *
from .features_managers import *
from .objective_managers import *
from itertools import product

def safe_product(update, constraint):
    if update is not None and constraint is not None:
        if len(update) > 0 and len(constraint) > 0:
            return product(update, constraint)
        if len(update) > 0:
            return ((u, None) for u in update)
        if len(constraint) > 0:
            return ((None, c) for c in constraint)
    if update is not None and len(update) > 0:
        return ((u, None) for u in update)
    if constraint is not None and len(constraint) > 0:
        return ((None, c) for c in constraint)
    return [(None, None)]



class SingleDepot():

    def __init__(self, converter, vehicles_info):
        self.converter = converter
        self.vehicles_info = vehicles_info
    
    def build_model(self, managers, objective_manager, expr_manager=None):
        self.objective_manager = objective_manager
        self.customer = self.converter.model.add_object_type(number=len(self.converter.nodes))
        self.location = self.converter.model.add_element_var(object_type = self.customer, target=self.converter.node_data["depots"][-1])
        
        if self.converter.model.float_cost:
            self.placeholder = dp.FloatExpr.state_cost()
        else:
            self.placeholder = dp.IntExpr.state_cost()

        match self.vehicles_info:
            case "multi_types":
                self.vehicle_type = self.converter.model.add_object_type(number = len(self.converter.vehicle_data["vehicles"]))
                self.vehicles = self.converter.model.add_element_var(object_type=self.vehicle_type, target=0)
                self.vehicles_index = self.converter.model.add_element_table(self.converter.vehicle_data["vehicles"])
                self.vehicle_type_skip = self.converter.model.add_element_table(self.converter.vehicle_data["skip"])
            case "tsp":
                pass
            case "single_type":
                self.vehicles = self.converter.model.add_int_resource_var(target=0, less_is_better=True)

        if expr_manager is not None:
            expr_manager._expand_model()

        self._set_objective_manager()

        for manager in managers:
            t = None
            if isinstance(manager, TimeWindowsManager):
                if manager.use_distance and isinstance(objective_manager, DistanceManager):
                    t = objective_manager.distance
                elif not manager.use_distance and isinstance(objective_manager, TimeManager):
                    t = objective_manager.time
            manager.expand_model(t)
            if isinstance(manager, VisitManager):
                self.unvisited = manager.get_mandatory_nodes()

        self.converter.model.add_base_case([self.unvisited.is_empty(), self.location == self.converter.node_data["depots"][-1]])

        self._define_transitions(managers, expr_manager)

        self._define_state_constraints(managers, expr_manager)

        self.bounds = self._define_dual_bound()

    def _set_objective_manager(self):
        if not isinstance(self.objective_manager, ExpressionsManager):
            self.objective_manager.set_objective()

    def _define_transitions(self, managers, expr_manager):
        self._define_visit_transition(managers, expr_manager)
        if self.vehicles_info != "tsp":
            if isinstance(self.objective_manager, ExpressionsManager):
                self._define_multiple_change_vehicle_transition(managers, expr_manager)
            else:
                self._define_change_vehicle_transition(managers, expr_manager)
        if self.vehicles_info == "multi_types":
            self._define_skip_transition()
        if isinstance(self.objective_manager, ExpressionsManager):
            self._define_multiple_return_transition(managers, expr_manager)
        else:
            self._define_return_transition(managers, expr_manager)

    
    def _define_skip_transition(self):
        skip = dp.Transition(
            name = f"Skip",
            cost = self.placeholder,
            effects = [
                (self.vehicles, self.vehicle_type_skip[self.vehicles_index[self.vehicles]])
            ],
            preconditions = [
                self.location == self.converter.node_data["depots"][-1],
                self.vehicles < self.vehicle_type_skip[self.vehicles_index[self.vehicles]]
            ]
        )
        self.converter.model.add_transition(skip)

            
    def _define_visit_transition(self, managers, expr_manager):
        if expr_manager is None or not expr_manager.has_edges:
            for j in self.converter.node_data["customers"]:
                visit = dp.Transition(
                    name = f"Visit {j}",
                    cost = self.placeholder,
                    effects = [
                        (self.location, j)
                    ],
                    preconditions = [] 
                )
                for manager in managers:
                    manager.manage_transition(visit, self.location, j, "visit")
                if expr_manager is not None:
                    expr_manager.manage_transition(visit, self.location, j, "visit")
                if self.objective_manager != expr_manager:
                    self.objective_manager.define_transition_cost(self.location, j, "visit", visit, True)
                self.converter.model.add_transition(visit)
        else:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            for j in self.converter.node_data["customers"]:
                for index, (update, constraint) in enumerate(safe_product(updates[j], constraints[j])):
                    visit = dp.Transition(
                        name = f"Visit {j} index {index}",
                        cost = self.placeholder,
                        effects = [
                            (self.location, j)
                        ],
                        preconditions = []
                    )
                    for manager in managers:
                        manager.manage_transition(visit, self.location, j, "visit")
                    expr_manager.manage_transition(visit, self.location, j, "visit", update, constraint)
                    if self.objective_manager != expr_manager:
                        self.objective_manager.define_transition_cost(self.location, j, "visit", visit, True)
                    self.converter.model.add_transition(visit)

    def _define_change_vehicle_transition(self, managers, expr_manager):
        if expr_manager is not None:
            if expr_manager.has_edges:
                updates = expr_manager.edge_updates
                constraints = expr_manager.edge_constraints
                for index, (update,constraint) in enumerate(safe_product(updates[self.converter.node_data["depots"][-1]], constraints[self.converter.node_data["depots"][-1]])):
                    change_vehicle = dp.Transition(
                        name = f"Change vehicle with index {index}",
                        cost = self.placeholder,
                        effects = [
                                (self.location, self.converter.node_data["depots"][-1]),
                                (self.vehicles, self.vehicles+1)
                            ],
                            preconditions = [
                                self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                                self.location != self.converter.node_data["depots"][-1],
                                ~self.unvisited.is_empty()
                            ]
                    )
                    for manager in managers:
                        manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
                    expr_manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle", update, constraint)
                    self.objective_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "change_vehicle", change_vehicle, True)
                    self.converter.model.add_transition(change_vehicle)
            else:
                change_vehicle = dp.Transition(
                    name = f"Change vehicle",
                    cost = self.placeholder,
                    effects = [
                            (self.location, self.converter.node_data["depots"][-1]),
                            (self.vehicles, self.vehicles+1)
                    ],
                    preconditions = [
                        self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                        self.location != self.converter.node_data["depots"][-1],
                        ~self.unvisited.is_empty()
                    ]
                )
                for manager in managers:
                    manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
                expr_manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
                self.objective_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "change_vehicle", change_vehicle, True)
                self.converter.model.add_transition(change_vehicle)
        else:
            change_vehicle = dp.Transition(
                name = f"Change vehicle",
                cost = self.placeholder,
                effects = [
                        (self.location, self.converter.node_data["depots"][-1]),
                        (self.vehicles, self.vehicles+1)
                ],
                preconditions = [
                    self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                    self.location != self.converter.node_data["depots"][-1],
                    ~self.unvisited.is_empty()
                ]
            )
            for manager in managers:
                manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
            self.objective_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "change_vehicle", change_vehicle, True)
            self.converter.model.add_transition(change_vehicle)

    def _define_multiple_change_vehicle_transition(self, managers, expr_manager):
        if expr_manager.has_edges:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            obj_vars = expr_manager.obj_var
            for index, (update,constraint) in enumerate(safe_product(updates[self.converter.node_data["depots"][-1]], constraints[self.converter.node_data["depots"][-1]])):
                for obj_index, obj_var in enumerate(obj_vars):
                    change_vehicle = dp.Transition(
                        name = f"Change vehicle with index {index} and objective {obj_index}",
                        cost = self.placeholder,
                        effects = [
                            (self.location, self.converter.node_data["depots"][-1]),
                            (self.vehicles, self.vehicles+1)
                        ],
                        preconditions = [
                            self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                            self.location != self.converter.node_data["depots"][-1],
                            ~self.unvisited.is_empty(),
                        ]
                    )
                    for manager in managers:
                        manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
                    expr_manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle", update, constraint)
                    expr_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "change_vehicle", change_vehicle, True, obj_var, self.vehicles)
                    self.converter.model.add_transition(change_vehicle)
        else:
            obj_vars = expr_manager.obj_var
            for obj_index, obj_var in enumerate(obj_vars):
                change_vehicle = dp.Transition(
                    name = f"Change vehicle with objective {obj_index}",
                    cost = self.placeholder,
                    effects = [
                        (self.location, self.converter.node_data["depots"][-1]),
                        (self.vehicles, self.vehicles+1)
                    ],
                    preconditions = [
                        self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                        self.location != self.converter.node_data["depots"][-1],
                        ~self.unvisited.is_empty()
                    ]
                )
                for manager in managers:
                    manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
                expr_manager.manage_transition(change_vehicle, self.location, self.converter.node_data["depots"][-1], "change_vehicle")
                expr_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "change_vehicle", change_vehicle, True, obj_var, self.vehicles)
                self.converter.model.add_transition(change_vehicle)

            
    def _define_return_transition(self, managers, expr_manager):
        if expr_manager is None or not expr_manager.has_edges:
            return_to_depot = dp.Transition(
                name = "return",
                cost = self.placeholder,
                effects = [
                    (self.location, self.converter.node_data["depots"][-1])
                ],
                preconditions = [
                    self.unvisited.is_empty(), 
                    self.location != self.converter.node_data["depots"][-1]
                ]
            )
            for manager in managers:
                manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return")
            if expr_manager is not None:
                expr_manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return")
            self.objective_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "return", return_to_depot, True)
            self.converter.model.add_transition(return_to_depot)
        else:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            for index, (update,constraint) in enumerate(safe_product(updates[self.converter.node_data["depots"][-1]],constraints[self.converter.node_data["depots"][-1]])):
                return_to_depot = dp.Transition(
                    name = f"return with index {index}",
                    cost = self.placeholder,
                    effects = [
                            (self.location, self.converter.node_data["depots"][-1]),
                        ],
                        preconditions = [
                            self.unvisited.is_empty(),
                            self.location != self.converter.node_data["depots"][-1]
                        ]
                )
                for manager in managers:
                    manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return")
                expr_manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return", update, constraint)
                self.objective_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "return", return_to_depot, True)
                self.converter.model.add_transition(return_to_depot)

    def  _define_multiple_return_transition(self, managers, expr_manager):
        if not expr_manager.has_edges:
            for obj_index, obj_var in enumerate(expr_manager.obj_var):
                return_to_depot = dp.Transition(
                    name = f"return with objective {obj_index}",
                    cost = self.placeholder,
                    effects = [
                        (self.location, self.converter.node_data["depots"][-1])
                    ],
                    preconditions = [
                        self.unvisited.is_empty(), 
                        self.location != self.converter.node_data["depots"][-1]
                    ]
                )
                for manager in managers:
                    manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return")
                if expr_manager is not None:
                    expr_manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return")
                expr_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "return", return_to_depot, True, obj_var, self.vehicles)
                self.converter.model.add_transition(return_to_depot)
        else:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            for index, (update,constraint) in enumerate(safe_product(updates[self.converter.node_data["depots"][-1]],constraints[self.converter.node_data["depots"][-1]])):
                for obj_index, obj_var in enumerate(expr_manager.obj_var):
                    return_to_depot = dp.Transition(
                        name = f"return with index {index} and with objective {obj_index}",
                        cost = self.placeholder,
                        effects = [
                                (self.location, self.converter.node_data["depots"][-1]),
                            ],
                            preconditions = [
                                self.unvisited.is_empty(),
                                self.location != self.converter.node_data["depots"][-1]
                            ]
                    )
                    for manager in managers:
                        manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return")
                    expr_manager.manage_transition(return_to_depot, self.location, self.converter.node_data["depots"][-1], "return", update, constraint)
                    expr_manager.define_transition_cost(self.location, self.converter.node_data["depots"][-1], "return", return_to_depot, True, obj_var, self.vehicles)
                    self.converter.model.add_transition(return_to_depot)

    def _define_state_constraints(self, managers, expr_manager):
        must_visit = None
        for manager in managers:
            if isinstance(manager, PickUpAndDeliveryManager) and manager.successors is not None:
                must_visit = manager.must_visit

        for manager in managers:
            manager.manage_state_constraints(must_visit, self.unvisited)

        if expr_manager is not None:
            expr_manager.manage_state_constraints(self.unvisited)

    def _define_dual_bound(self):
        return self.objective_manager.define_dual_bounds(self.unvisited)

    


class MultiDepot():

    def __init__(self, converter, vehicles_info):
        self.converter = converter
        self.vehicles_info = vehicles_info
        self.dummy_depot = self._add_dummy_depot()


    def _add_dummy_depot(self):
        dummy_depot = self.converter.routing_model.add_node(id = len(self.converter.routing_model.get_nodes()), depot = True)
        for node in self.converter.routing_model.get_nodes()[:-1]:
            if node.depot:
                self.converter.routing_model.add_edge(node_from=dummy_depot, node_to=node)
                self.converter.routing_model.add_edge(node_from=node, node_to=dummy_depot)
        return dummy_depot
    
    def build_model(self, managers, objective_manager, expr_manager=None):
        self.objective_manager = objective_manager
        self.customer = self.converter.model.add_object_type(number=len(self.converter.nodes))
        self.location = self.converter.model.add_element_var(object_type = self.customer, target=self.converter.node_data["depots"][-1])
        
        if self.converter.model.float_cost:
            self.placeholder = dp.FloatExpr.state_cost()
        else:
            self.placeholder = dp.IntExpr.state_cost()
        

        match self.vehicles_info:
            case "multi_types":
                self.vehicle_type = self.converter.model.add_object_type(number = len(self.converter.vehicle_data["vehicles"]))
                self.vehicles = self.converter.model.add_element_var(object_type=self.vehicle_type, target=0)
                self.vehicles_index = self.converter.model.add_element_table(self.converter.vehicle_data["vehicles"])
                self.allowed_starts = self.converter.model.add_set_table(self.converter.vehicle_data["allowed_starts"], object_type = self.customer)
                self.allowed_ends = self.converter.model.add_set_table(self.converter.vehicle_data["allowed_ends"], object_type = self.customer)
                self.vehicle_type_skip = self.converter.model.add_element_table(self.converter.vehicle_data["skip"])
            case "tsp":
                self.allowed_starts = self.converter.vehicle_data["allowed_starts"][0]
                self.allowed_ends = self.converter.vehicle_data["allowed_ends"][0]
            case "single_type":
                self.vehicles = self.converter.model.add_int_resource_var(target=0, less_is_better=True)
                self.allowed_starts = self.converter.vehicle_data["allowed_starts"][0]
                self.allowed_ends = self.converter.vehicle_data["allowed_ends"][0]

        if expr_manager is not None:
            expr_manager._expand_model()

        self._set_objective_manager()

        for manager in managers:
            t = None
            if isinstance(manager, TimeWindowsManager):
                if manager.use_distance and isinstance(objective_manager, DistanceManager):
                    t = objective_manager.distance
                elif not manager.use_distance and isinstance(objective_manager, TimeManager):
                    t = objective_manager.time
            manager.expand_model(t)
            if isinstance(manager, VisitManager):
                self.unvisited = manager.get_mandatory_nodes()

        self.converter.model.add_base_case([self.unvisited.is_empty(), self.location == self.converter.node_data["depots"][-1]])

        self._define_transitions(managers, expr_manager)

        self._define_state_constraints(managers, expr_manager)

        self.bounds = self._define_dual_bound()

    def _set_objective_manager(self):
        if not isinstance(self.objective_manager, ExpressionsManager):
            self.objective_manager.set_objective()

    def _define_transitions(self, managers, expr_manager):
        self._define_start_transition(managers, expr_manager)
        self._define_visit_transition(managers, expr_manager)
        if self.vehicles_info!= "tsp":
            self._define_change_vehicle_transition(managers, expr_manager)
        if self.vehicles_info == "multi_types":
            self._define_skip_transition()
        self._define_return_transition(managers, expr_manager)

    def _define_skip_transition(self):
        skip = dp.Transition(
            name = f"Skip",
            cost = self.placeholder,
            effects = [
                (self.vehicles, self.vehicle_type_skip[self.vehicles_index[self.vehicles]])
            ],
            preconditions = [
                self.location == self.converter.node_data["depots"][-1],
                self.vehicles < self.vehicle_type_skip[self.vehicles_index[self.vehicles]]
            ]
        )
        self.converter.model.add_transition(skip)

    def _define_start_transition(self, managers, expr_manager):
        for depot in self.converter.node_data["depots"][:-1]:
            if self.vehicle_type == "multi_types":
                allowed_start = self.allowed_starts[self.vehicles_index[self.vehicles]].contains(depot)
                start_path = dp.Transition(
                    name = f"start at depot {depot}",
                    cost = self.placeholder,
                    effects = [
                        (self.location, depot)
                    ],
                    preconditions = [
                        self.location == self.converter.node_data["depots"][-1],
                        allowed_start
                    ]
                )
            else:
                if depot in self.allowed_starts:
                    start_path = dp.Transition(
                        name = f"start at depot {depot}",
                        cost = self.placeholder,
                        effects = [
                            (self.location, depot)
                        ],
                        preconditions = [
                            self.location == self.converter.node_data["depots"][-1]
                        ]
                    )
                else:
                    start_path = None
            if start_path is not None:
                for manager in managers:
                    manager.manage_transition(start_path, self.location, depot, "start_path")
                self.objective_manager.define_transition_cost(self.location, depot, "start_path", start_path, False)
                self.converter.model.add_transition(start_path)

    def _define_visit_transition(self, managers, expr_manager):
        if expr_manager is None or not expr_manager.has_edges:
            for j in self.converter.node_data["customers"]:
                visit = dp.Transition(
                    name = f"visit {j}",
                    cost = self.placeholder,
                    effects = [
                        (self.location, j)
                    ],
                    preconditions = [
                        self.location != self.converter.node_data["depots"][-1]
                    ]
                )
                for manager in managers:
                    manager.manage_transition(visit, self.location, j, "visit")
                if expr_manager is not None:
                    expr_manager.manage_transition(visit, self.location, j, "visit")
                self.objective_manager.define_transition_cost(self.location, j, "visit", visit, False)
                self.converter.model.add_transition(visit)
        else:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            for j in self.converter.node_data["customers"]:
                for index, (update,constraint) in enumerate(safe_product(updates[j],constraints[j])):
                    visit = dp.Transition(
                        name = f"Visit {j} with index {index}",
                        cost = self.placeholder,
                        effects = [
                            (self.location, j)
                        ],
                        preconditions = [
                            self.location != self.converter.node_data["depots"][-1]
                        ] 
                    )
                    for manager in managers:
                        manager.manage_transition(visit, self.location, j, "visit")
                    expr_manager.manage_transition(visit, self.location, j, "visit", update, constraint)
                    self.objective_manager.define_transition_cost(self.location, j, "visit", visit, False)
                    self.converter.model.add_transition(visit)
            
    def _define_change_vehicle_transition(self, managers, expr_manager):
        if expr_manager is None or not expr_manager.has_edges:
            for depot in self.converter.node_data["depots"][:-1]:
                if self.vehicle_type == "multi_types":
                    allowed_end = self.allowed_ends[self.vehicles_index[self.vehicles]].contains(depot)
                    change_vehicle = dp.Transition(
                        name = f"change vehicle at depot {depot}",
                        cost = self.placeholder,
                        effects = [
                            (self.location, self.converter.node_data["depots"][-1]),
                            (self.vehicles, self.vehicles + 1),
                        ],
                        preconditions = [
                            ~self.unvisited.is_empty(),
                            self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                            allowed_end
                        ] + [self.location != d for d in self.converter.node_data["depots"]]
                    )
                else:
                    if depot in self.allowed_ends:
                        change_vehicle = dp.Transition(
                            name = f"change vehicle at depot {depot}",
                            cost = self.placeholder,
                            effects = [
                                (self.location, self.converter.node_data["depots"][-1]),
                                (self.vehicles, self.vehicles + 1),
                            ],
                            preconditions = [
                                ~self.unvisited.is_empty(),
                                self.vehicles < len(self.converter.vehicle_data["vehicles"])-1
                            ] + [self.location != d for d in self.converter.node_data["depots"]]
                        )
                    else:
                        change_vehicle = None
                if change_vehicle is not None:
                    for manager in managers:
                            manager.manage_transition(change_vehicle, self.location, depot, "change_vehicle")
                    if expr_manager is not None:
                        expr_manager.manage_transition(change_vehicle, self.location, depot, "change_vehicle")
                    self.objective_manager.define_transition_cost(self.location, depot, "change_vehicle", change_vehicle, False)
                    self.converter.model.add_transition(change_vehicle)
        else:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            for depot in self.converter.node_data["depots"][:-1]:
                    if self.vehicle_type == "multi_types":
                        allowed_end = self.allowed_ends[self.vehicles_index[self.vehicles]].contains(depot)
                        for index, (update,constraint) in enumerate(safe_product(updates[depot],constraints[depot])):
                            change_vehicle = dp.Transition(
                                name = f"Change vehicle at depot {depot} with index {index}" ,
                                cost = self.placeholder,
                                effects = [
                                        (self.location, self.converter.node_data["depots"][-1]),
                                        (self.vehicles, self.vehicles+1)
                                    ],
                                    preconditions = [
                                        self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                                        allowed_end,
                                        ~self.unvisited.is_empty()
                                    ] + [self.location != d for d in self.converter.node_data["depots"]]
                            )
                    else:
                        if depot in self.allowed_ends:
                            for index, (update,constraint) in enumerate(safe_product(updates[depot],constraints[depot])):
                                change_vehicle = dp.Transition(
                                name = f"Change vehicle at depot {depot} with index {index}" ,
                                cost = self.placeholder,
                                effects = [
                                        (self.location, self.converter.node_data["depots"][-1]),
                                        (self.vehicles, self.vehicles+1)
                                    ],
                                    preconditions = [
                                        self.vehicles < len(self.converter.vehicle_data["vehicles"])-1,
                                        ~self.unvisited.is_empty()
                                    ] + [self.location != d for d in self.converter.node_data["depots"]]
                            )
                        else:
                            change_vehicle = None
                        if change_vehicle is not None:
                            for manager in managers:
                                manager.manage_transition(change_vehicle, self.location, depot, "change_vehicle")
                            expr_manager.manage_transition(change_vehicle, self.location, depot, "change_vehicle", update, constraint)
                            self.objective_manager.define_transition_cost(self.location, depot, "change_vehicle", change_vehicle, False)
                            self.converter.model.add_transition(change_vehicle) 

    def _define_return_transition(self, managers, expr_manager):
        if expr_manager is None or not expr_manager.has_edges:
            for depot in self.converter.node_data["depots"][:-1]:
                if self.vehicle_type == "multi_types":
                    allowed_end = self.allowed_ends[self.vehicles_index[self.vehicles]].contains(depot)
                    return_to_depot = dp.Transition(
                        name = f"return to depot {depot}",
                        cost = self.placeholder,
                        effects = [
                            (self.location, self.converter.node_data["depots"][-1]),
                        ],
                        preconditions = [
                            self.unvisited.is_empty(),
                            allowed_end
                        ] + [self.location != d for d in self.converter.node_data["depots"]]
                    )
                else:
                    if depot in self.allowed_ends:
                        return_to_depot = dp.Transition(
                            name = f"return to depot {depot}",
                            cost = self.placeholder,
                            effects = [
                                (self.location, self.converter.node_data["depots"][-1]),
                            ],
                            preconditions = [
                                self.unvisited.is_empty(),
                            ] + [self.location != d for d in self.converter.node_data["depots"]]
                        )
                    else:
                        return_to_depot = None
                if return_to_depot is not None:
                    for manager in managers:
                            manager.manage_transition(return_to_depot, self.location, depot, "return")
                    if expr_manager is not None:
                        expr_manager.manage_transition(return_to_depot, self.location, depot, "return")
                    self.objective_manager.define_transition_cost(self.location, depot, "return", return_to_depot, False)
                    self.converter.model.add_transition(return_to_depot)
        else:
            updates = expr_manager.edge_updates
            constraints = expr_manager.edge_constraints
            print(updates, constraints)
            for depot in self.converter.node_data["depots"][:-1]:
                if self.vehicle_type == "multi_types":
                    allowed_end = self.allowed_ends[self.vehicles_index[self.vehicles]].contains(depot)
                    for index, (update,constraint) in enumerate(safe_product(updates[depot],constraints[depot])):
                        return_to_depot = dp.Transition(
                            name = f"Return to depot {depot} with index {index}",
                            cost = self.placeholder,
                            effects = [
                                    (self.location, self.converter.node_data["depots"][-1]),
                                ],
                                preconditions = [
                                    self.unvisited.is_empty(),
                                    allowed_end
                                ] + [self.location != d for d in self.converter.node_data["depots"]]
                        )
                else:
                    if depot in self.allowed_ends:
                        for index, (update,constraint) in enumerate(safe_product(updates[depot],constraints[depot])):
                            return_to_depot = dp.Transition(
                                name = f"Return to depot {depot} with index {index}",
                                cost = self.placeholder,
                                effects = [
                                        (self.location, self.converter.node_data["depots"][-1]),
                                    ],
                                    preconditions = [
                                        self.unvisited.is_empty()
                                    ] + [self.location != d for d in self.converter.node_data["depots"]]
                            )
                    else:
                        return_to_depot = None
                    if return_to_depot is not None:
                        for manager in managers:
                            manager.manage_transition(return_to_depot, self.location, depot, "return")
                        expr_manager.manage_transition(return_to_depot, self.location, depot, "return", update, constraint)
                        self.objective_manager.define_transition_cost(self.location, depot, "return", return_to_depot, False)
                        self.converter.model.add_transition(return_to_depot) 

    def _define_state_constraints(self, managers, expr_manager):
        must_visit = None
        for manager in managers:
            if isinstance(manager, PickUpAndDeliveryManager) and manager.successors is not None:
                must_visit = manager.must_visit

        for manager in managers:
            manager.manage_state_constraints(must_visit, self.unvisited)

        if expr_manager is not None:
            expr_manager.manage_state_constraints(self.unvisited)

    def _define_dual_bound(self, objective_manager):
        return objective_manager.define_dual_bounds(self.unvisited)

