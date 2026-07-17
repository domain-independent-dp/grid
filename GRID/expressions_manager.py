import didppy as dp

from .expressions import Const, Expr, SetConst, SetElem, SetVar, Var


def convert_op(op: str, left: Expr, right: Expr):
    match op:
        case "<=":
            return left <= right
        case "<":
            return left < right
        case ">=":
            return left >= right
        case ">":
            return left > right
        case "==":
            return left == right
        case "!=":
            return left != right
        case "pos":
            return left
        case "neg":
            return -left
        case "+":
            return left + right
        case "-":
            return left - right
        case "*":
            return left * right
        case "/":
            return left / right
        case "//":
            return left // right
        case "%":
            return left % right
        case "&":
            return left & right
        case "|":
            return left | right
        case "~":
            return ~left
        case "max":
            return dp.max(left, right)
        case "min":
            return dp.min(left, right)
        case "log":
            return dp.log(left, right)
        case "sqrt":
            return dp.sqrt(left, right)
        case "add":
            return left.add(right)
        case "contains":
            return left.contains(right)
        case "empty":
            return left.is_empty()
        case "len":
            return left.len()
        case "remove":
            return left.remove(right)


def extract_constants(caller, tables, expression, tr_id, location, j):
    if isinstance(expression, (Var, SetVar)):
        pass
    elif isinstance(expression, Const):
        caller.const_id += 1
        tables[(tr_id, location, j, caller.const_id)] = expression.value
    elif isinstance(expression, Expr):
        extract_constants(caller, tables, expression.left, tr_id, location, j)
        extract_constants(caller, tables, expression.right, tr_id, location, j)


class Update:
    def __init__(self, transition, location, j):
        self.locations = set([location])
        self.n_locations = 1
        self.vars_set = set([transition.var.id])
        self.transitions = [transition]
        self.int_tables = {}
        self.float_tables = {}
        self.const_id = -1
        if transition.numeric_type == "integer":
            extract_constants(self, self.int_tables, transition.expression, 0, location, j)
        else:
            extract_constants(self, self.float_tables, transition.expression, 0, location, j)

    def add_transition(self, transition, location, j):
        self.vars_set.add(transition.var.id)
        self.transitions.append(transition)
        self.const_id = -1
        if transition.numeric_type == "integer":
            extract_constants(
                self, self.int_tables, transition.expression, len(self.transitions) - 1, location, j
            )
        else:
            extract_constants(
                self,
                self.float_tables,
                transition.expression,
                len(self.transitions) - 1,
                location,
                j,
            )

    def merge(self, effect):
        self.locations.update(effect.locations)
        self.n_locations = len(self.locations)
        for old_id, old_t in enumerate(effect.transitions):
            for t_id, t in enumerate(self.transitions):
                if old_t == t:
                    for (id, location, j, c_id), value in effect.int_tables.items():
                        if id == old_id:
                            self.int_tables[(t_id, location, j, c_id)] = value
                    for (id, location, j, c_id), value in effect.float_tables.items():
                        if id == old_id:
                            self.float_tables[(t_id, location, j, c_id)] = value

    def _to_didp(self, didp_model, customer_type):
        self.locations = didp_model.create_set_const(
            object_type=customer_type, value=self.locations
        )
        if len(self.int_tables) > 0:
            self.int_tables = didp_model.add_int_table(self.int_tables, default=0)
        if len(self.float_tables) > 0:
            self.float_tables = didp_model.add_float_table(self.float_tables, default=0)

    def __eq__(self, other):
        same_vars = self.vars_set == other.vars_set
        if not same_vars:
            return False
        else:
            for t in self.transitions:
                search = False
                for other_t in other.transitions:
                    search = search or other_t == t
                if not search:
                    return False
        return True

    def generate_effects(self, location, j, depots, vehicle, vehicle_vars, didp_vars):
        effects = {}
        if j not in depots:
            for i, transition in enumerate(self.transitions):
                if transition.numeric_type == "integer":
                    table = self.int_tables
                else:
                    table = self.float_tables
                self.const_id = -1
                if vehicle is not None:
                    if transition.var in vehicle_vars.keys():
                        effects[transition.var] = (
                            vehicle_vars[transition.var] == vehicle
                        ).if_then_else(
                            self._visit_transition(
                                transition.expression, i, location, j, didp_vars, table
                            ),
                            didp_vars[transition.var],
                        )
                    else:
                        effects[transition.var] = self._visit_transition(
                            transition.expression, i, location, j, didp_vars, table
                        )
                else:
                    effects[transition.var] = self._visit_transition(
                        transition.expression, i, location, j, didp_vars, table
                    )
        else:
            for i, transition in enumerate(self.transitions):
                if transition.numeric_type == "integer":
                    table = self.int_tables
                else:
                    table = self.float_tables
                self.const_id = -1
                if vehicle is not None:
                    if transition.var in vehicle_vars.keys():
                        effects[transition.var] = [
                            transition.var.initial_value,
                            (vehicle_vars[transition.var] == vehicle).if_then_else(
                                self._visit_transition(
                                    transition.expression, i, location, j, didp_vars, table
                                ),
                                didp_vars[transition.var],
                            ),
                        ]
                    else:
                        effects[transition.var] = self._visit_transition(
                            transition.expression, i, location, j, didp_vars, table
                        )
                else:
                    if transition.var in vehicle_vars.keys():
                        effects[transition.var] = [
                            transition.var.initial_value,
                            self._visit_transition(
                                transition.expression, i, location, j, didp_vars, table
                            ),
                        ]
                    else:
                        effects[transition.var] = self._visit_transition(
                            transition.expression, i, location, j, didp_vars, table
                        )
        return effects

    def _visit_transition(self, expression, tr_id, location, j, didp_vars, table):
        if isinstance(expression, (Var, SetVar)):
            return didp_vars[expression]
        if isinstance(expression, Const):
            self.const_id += 1
            return table[tr_id, location, j, self.const_id]
        op = expression.op
        left = expression.left
        right = expression.right
        return convert_op(
            op,
            self._visit_transition(left, tr_id, location, j, didp_vars, table),
            self._visit_transition(right, tr_id, location, j, didp_vars, table),
        )


class Constraint:
    def __init__(self, constraint, location, j):
        self.locations = set([location])
        self.n_locations = 1
        self.constraints = [constraint]
        self.int_tables = {}
        self.float_tables = {}
        self.const_id = -1
        if constraint.numeric_type == "integer":
            extract_constants(self, self.int_tables, constraint.expression, 0, location, j)
        else:
            extract_constants(self, self.float_tables, constraint.expression, 0, location, j)

    def add_constraint(self, constraint, location, j):
        self.constraints.append(constraint)
        self.const_id = -1
        if constraint.numeric_type == "integer":
            extract_constants(
                self, self.int_tables, constraint.expression, len(self.constraints) - 1, location, j
            )
        else:
            extract_constants(
                self,
                self.float_tables,
                constraint.expression,
                len(self.constraints) - 1,
                location,
                j,
            )

    def merge(self, constraint):
        self.locations.update(constraint.locations)
        self.n_locations = len(self.locations)
        for old_id, old_c in enumerate(constraint.constraints):
            for t_id, c in enumerate(self.constraints):
                if old_c == c:
                    for (id, location, j, c_id), value in constraint.int_tables.items():
                        if id == old_id:
                            self.int_tables[(t_id, location, j, c_id)] = value
                    for (id, location, j, c_id), value in constraint.float_tables.items():
                        if id == old_id:
                            self.float_tables[(t_id, location, j, c_id)] = value

    def _to_didp(self, didp_model, customer_type):
        self.locations = didp_model.create_set_const(
            object_type=customer_type, value=self.locations
        )
        if len(self.int_tables) > 0:
            self.int_tables = didp_model.add_int_table(self.int_tables, default=0)
        if len(self.float_tables) > 0:
            self.float_tables = didp_model.add_float_table(self.float_tables, default=0)

    def __eq__(self, other):
        for c in self.constraints:
            search = False
            for other_c in other.constraints:
                search = search or other_c == c
            if not search:
                return False
        return True

    def generate_preconditions(self, location, j, didp_vars, vehicle_vars, vehicle):
        preconditions = []
        self.vehicles_pre = []
        for i, constraint in enumerate(self.constraints):
            if constraint.numeric_type == "integer":
                table = self.int_tables
            else:
                table = self.float_tables
            self.const_id = -1
            if vehicle is not None:
                self.vehicles_pre = []
            pre = self._visit_transition(
                constraint.expression, i, location, j, didp_vars, table, vehicle_vars, vehicle
            )
            if len(self.vehicles_pre) > 0:
                vehicles_ors = self.vehicles_pre[0]
                for i in range(1, len(self.vehicles_pre)):
                    vehicles_ors = vehicles_ors | self.vehicles_pre[i]
                pre = ~vehicles_ors | pre
            preconditions.append(pre)
        return preconditions

    def _visit_transition(
        self, expression, c_id, location, j, didp_vars, table, vehicle_vars, vehicle
    ):
        if isinstance(expression, (Var, SetVar)):
            if vehicle is not None:
                self.vehicles_pre.append(vehicle == vehicle_vars[expression])
            return didp_vars[expression]
        elif isinstance(expression, Const):
            self.const_id += 1
            return table[c_id, location, j, self.const_id]
        op = expression.op
        left = expression.left
        right = expression.right
        return convert_op(
            op,
            self._visit_transition(
                left, c_id, location, j, didp_vars, table, vehicle_vars, vehicle
            ),
            self._visit_transition(
                right, c_id, location, j, didp_vars, table, vehicle_vars, vehicle
            ),
        )


class ExpressionsManager:
    def __init__(
        self,
        converter,
        vehicle_vars,
        model_vars,
        model_constraints,
        edge_updates,
        edge_constraints,
        node_updates,
        node_constraints,
        vehicles_info,
    ):
        self.converter = converter
        self.structure = converter.structure
        self.vehicles_info = vehicles_info
        self.vehicle_vars = vehicle_vars
        self.model_vars = model_vars
        self.edge_updates = edge_updates
        self.edge_constraints = edge_constraints
        self.node_updates = node_updates
        self.node_constraints = node_constraints
        self.model_constraints = model_constraints
        self.has_edges = self.edge_updates is not None or self.edge_constraints is not None
        self.obj_var = None
        self.didp_set_const = {}
        self.from_node_id_to_idx = self.converter.node_data["from_node_id_to_idx"]

    def set_objective(self, aggregation, dual_bounds, obj):
        self.aggregation = aggregation
        self.dual_bounds = dual_bounds
        self.multiple_vars = isinstance(obj, list)
        if self.multiple_vars:
            self.obj_var = obj
        else:
            self.obj_var = [obj]

    def _compute_total_location_per_node(self):
        n_locations_per_node = {}
        customers = self.converter.node_data["customers"]
        depots = self.converter.node_data["depots"]
        total_nodes = depots + customers
        connections = self.converter.edge_data["connections"]
        if connections is None:
            n_locations_per_node = {j: len(total_nodes) - 1 for j in total_nodes}
        else:
            for j in total_nodes:
                n_locations_per_node[j] = len(
                    [(node, j) for node in total_nodes if node != j and connections[node][j]]
                )
        self.n_locations_per_node = n_locations_per_node

    def _expand_model(self):
        self.didp_vars = self._manage_vars()
        if self.edge_updates is not None:
            self.edge_updates = self._extract_transitions(self.edge_updates, type="effect")
            for updates in self.edge_updates:
                for update in updates:
                    update._to_didp(self.converter.model, self.structure.customer)
        else:
            self.edge_updates = [[None] for _ in range(len(self.converter.nodes))]
        if self.edge_constraints is not None:
            self.edge_constraints = self._extract_transitions(
                self.edge_constraints, type="constraint"
            )
            for constraints in self.edge_constraints:
                for constraint in constraints:
                    constraint._to_didp(self.converter.model, self.structure.customer)
        else:
            self.edge_constraints = [[None] for _ in range(len(self.converter.nodes))]
        self._compute_total_location_per_node()

    def _manage_vars(self):
        didp_vars = {}
        for var in self.vehicle_vars.keys():
            if var.preference is None:
                if var.type == "integer":
                    didp_vars[var] = self.converter.model.add_int_var(target=var.initial_value)
                elif var.type == "float":
                    didp_vars[var] = self.converter.model.add_float_var(target=var.initial_value)
                else:
                    didp_vars[var] = self.converter.model.add_set_var(
                        object_type=self.structure.customer, target=var.initial_value
                    )
                    self.didp_set_const[frozenset(var.initial_value)] = (
                        self.converter.model.create_set_const(
                            object_type=self.structure.customer,
                            value=[self.from_node_id_to_idx[x] for x in var.initial_value],
                        )
                    )
            elif var.preference == "low":
                if var.type == "integer":
                    didp_vars[var] = self.converter.model.add_int_resource_var(
                        target=var.initial_value, less_is_better=True
                    )
                else:
                    didp_vars[var] = self.converter.model.add_float_resource_var(
                        target=var.initial_value, less_is_better=True
                    )
            else:
                if var.type == "integer":
                    didp_vars[var] = self.converter.model.add_int_resource_var(
                        target=var.initial_value, less_is_better=False
                    )
                else:
                    didp_vars[var] = self.converter.model.add_float_resource_var(
                        target=var.initial_value, less_is_better=False
                    )
        for var in self.model_vars:
            if var.preference is None:
                if var.type == "integer":
                    didp_vars[var] = self.converter.model.add_int_var(target=var.initial_value)
                elif var.type == "float":
                    didp_vars[var] = self.converter.model.add_float_var(target=var.initial_value)
                else:
                    didp_vars[var] = self.converter.model.add_set_var(
                        object_type=self.structure.customer, target=var.initial_value
                    )
            elif var.preference == "low":
                if var.type == "integer":
                    didp_vars[var] = self.converter.model.add_int_resource_var(
                        target=var.initial_value, less_is_better=True
                    )
                else:
                    didp_vars[var] = self.converter.model.add_float_resource_var(
                        target=var.initial_value, less_is_better=True
                    )
            else:
                if var.type == "integer":
                    didp_vars[var] = self.converter.model.add_int_resource_var(
                        target=var.initial_value, less_is_better=False
                    )
                else:
                    didp_vars[var] = self.converter.model.add_float_resource_var(
                        target=var.initial_value, less_is_better=False
                    )
        return didp_vars

    def _extract_transitions(self, transitions, type):
        cols = list(map(list, zip(*transitions, strict=False)))
        total_aggregation = []
        for j, col in enumerate(cols):
            aggregate_on_locations = []
            added = False
            for location, effects in enumerate(col):
                pattern = None
                created = False
                for e in effects:
                    if not created:
                        pattern = (
                            Update(e, location, j)
                            if type == "effect"
                            else Constraint(e, location, j)
                        )
                        created = True
                    else:
                        pattern.add_transition(
                            e, location, j
                        ) if type == "effect" else pattern.add_constraint(e, location, j)
                if created:
                    if not added:
                        aggregate_on_locations.append(pattern)
                        added = True
                    else:
                        merged = False
                        for i in range(len(aggregate_on_locations)):
                            old_pattern = aggregate_on_locations[i]
                            if old_pattern == pattern:
                                merged = True
                                old_pattern.merge(pattern)
                        if not merged:
                            aggregate_on_locations.append(pattern)
            total_aggregation.append(aggregate_on_locations)
        return total_aggregation

    def _visit_constraint(self, constraint, vehicle):
        if isinstance(constraint, (Var, SetVar)):
            if vehicle is not None:
                self.vehicles_pre.append(vehicle == self.vehicle_vars[constraint])
            return self.didp_vars[constraint]
        if isinstance(constraint, Const):
            return constraint.value
        if isinstance(constraint, SetElem):
            return self.from_node_id_to_idx[constraint.value]
        if isinstance(constraint, SetConst):
            didp_set_const = self.didp_set_const.get(frozenset(constraint.initial_value))
            if didp_set_const is None:
                didp_set_const = self.converter.model.create_set_const(
                    object_type=self.structure.customer,
                    value=[self.from_node_id_to_idx[x] for x in constraint.initial_value],
                )
                self.didp_set_const[frozenset(constraint.initial_value)] = didp_set_const
        op = constraint.op
        left = constraint.left
        right = constraint.right
        return convert_op(
            op, self._visit_constraint(left, vehicle), self._visit_constraint(right, vehicle)
        )

    def _visit_transition(self, expression):
        if isinstance(expression, (Var, SetVar)):
            return self.didp_vars[expression]
        if isinstance(expression, Const):
            return expression.value
        if isinstance(expression, SetElem):
            return self.from_node_id_to_idx[expression.value]
        if isinstance(expression, SetConst):
            didp_set_const = self.didp_set_const.get(frozenset(expression.initial_value))
            if didp_set_const is None:
                didp_set_const = self.converter.model.create_set_const(
                    object_type=self.structure.customer,
                    value=[self.from_node_id_to_idx[x] for x in expression.initial_value],
                )
                self.didp_set_const[frozenset(expression.initial_value)] = didp_set_const
            return didp_set_const
        op = expression.op
        left = expression.left
        right = expression.right
        return convert_op(op, self._visit_transition(left), self._visit_transition(right))

    def _generate_preconditions_node(self, j, vehicle):
        preconditions = []
        self.vehicles_pre = []
        if self.node_constraints is not None:
            for transition in self.node_constraints[j]:
                if vehicle is not None:
                    self.vehicles_pre = []
                pre = self._visit_constraint(transition.expression, vehicle)
                if len(self.vehicles_pre) > 0:
                    vehicles_ors = self.vehicles_pre[0]
                    for i in range(1, len(self.vehicles_pre)):
                        vehicles_ors = vehicles_ors | self.vehicles_pre[i]
                    pre = ~vehicles_ors | pre
                preconditions.append(pre)
        return preconditions

    def _generate_effects_node(self, j, vehicle):
        effects = {}
        if j not in self.converter.node_data["depots"]:
            for transition in self.node_updates[j]:
                if vehicle is not None:
                    if transition.var in self.vehicle_vars.keys():
                        effects[transition.var] = (
                            self.vehicle_vars[transition.var] == vehicle
                        ).if_then_else(
                            self._visit_transition(transition.expression),
                            self.didp_vars[transition.var],
                        )
                else:
                    effects[transition.var] = self._visit_transition(transition.expression)
        else:
            for transition in self.node_updates[j]:
                if vehicle is not None:
                    if transition.var in self.vehicle_vars.keys():
                        if transition.var.type == "setvar":
                            value = self.didp_set_const[frozenset(transition.var.initial_value)]
                        else:
                            value = transition.var.initial_value
                        effects[transition.var] = [
                            value,
                            (self.vehicle_vars[transition.var] == vehicle).if_then_else(
                                self._visit_transition(transition.expression),
                                self.didp_vars[transition.var],
                            ),
                        ]
                else:
                    if transition.var in self.vehicle_vars.keys():
                        if transition.var.type == "setvar":
                            value = self.didp_set_const[frozenset(transition.var.initial_value)]
                        else:
                            value = transition.var.initial_value
                        effects[transition.var] = [
                            value,
                            self._visit_transition(transition.expression),
                        ]
                    else:
                        effects[transition.var] = self._visit_transition(transition.expression)
        return effects

    def manage_transition(self, transition, location, j, type, update=None, constraint=None):
        if self.obj_var is not None:
            self.objective_effect = {}
        effects = {}
        preconditions = []

        if (
            update is not None
            and update.n_locations < self.n_locations_per_node[j]
            and constraint is not None
            and constraint.n_locations < self.n_locations_per_node[j]
        ):
            locations_set = update.locations.intersection(constraint.locations)
        elif update is not None and update.n_locations < self.n_locations_per_node[j]:
            locations_set = update.locations
        elif constraint is not None and constraint.n_locations < self.n_locations_per_node[j]:
            locations_set = constraint.locations
        else:
            locations_set = None

        if locations_set is not None:
            transition.add_precondition(locations_set.contains(location))

        if type == "change_vehicle":
            if self.vehicles_info == "multi_types":
                vehicle_index = self.structure.vehicles_index[self.structure.vehicles]
            else:
                vehicle_index = None
        else:
            if self.vehicles_info == "multi_types":
                vehicle_index = self.structure.vehicles_index[self.structure.vehicles]
            else:
                vehicle_index = None

        if j in self.converter.node_data["depots"]:
            for var in self.vehicle_vars.keys():
                if var.type == "setvar":
                    value = self.didp_set_const[frozenset(var.initial_value)]
                else:
                    value = var.initial_value
                if vehicle_index is not None:
                    effects[var] = (self.vehicle_vars[var] == vehicle_index).if_then_else(
                        value, self.didp_vars[var]
                    )
                else:
                    effects[var] = value

        if update is not None:
            effects.update(
                update.generate_effects(
                    location,
                    j,
                    self.converter.node_data["depots"],
                    vehicle_index,
                    self.vehicle_vars,
                    self.didp_vars,
                )
            )

        if self.node_updates is not None:
            effects.update(self._generate_effects_node(j, vehicle_index))

        if constraint is not None:
            preconditions.extend(
                constraint.generate_preconditions(
                    location, j, self.didp_vars, self.vehicle_vars, vehicle_index
                )
            )

        if self.node_constraints is not None:
            preconditions.extend(self._generate_preconditions_node(j, vehicle_index))

        for pre in preconditions:
            transition.add_precondition(pre)
        for var, effect in effects.items():
            if self.obj_var is not None:
                for v in self.obj_var:
                    if v.id == var.id:
                        self.objective_effect[v] = effect
            if isinstance(effect, list):
                effect = effect[0]
            if type != "return":
                transition.add_effect(self.didp_vars[var], effect)

    def manage_state_constraints(self, _):
        for c in self.model_constraints:
            self.converter.model.add_state_constr(self._visit_constraint(c.expression))

    def define_transition_cost(self, location, j, type, transition, single_depot, obj, vehicle):
        if self.vehicles_info == "multi_types":
            vehicle_index = self.structure.vehicles_index[self.structure.vehicles]
        else:
            vehicle_index = None
        effect = self.objective_effect.get(obj, None)
        if isinstance(effect, list):
            effect = effect[1]
        if effect is None:
            effect = self.didp_vars[obj]

        state_cost = self.structure.placeholder

        match self.aggregation:
            case "max":
                transition.cost = dp.max(state_cost, effect)
            case "total":
                transition.cost = state_cost + effect
            case None:
                transition.cost = effect
        self.objective_effect = {}

        if vehicle_index is not None:
            transition.add_precondition(self.vehicle_vars[obj] == vehicle_index)

    def define_dual_bounds(self, _):
        for bound in self.dual_bounds:
            self.converter.model.add_dual_bound(bound)
