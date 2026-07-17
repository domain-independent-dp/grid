import didppy as dp


class DistanceManager:
    def __init__(self, converter, aggregation):
        self.converter = converter
        self.structure = converter.structure
        self.aggregation = aggregation

    def set_objective(self):
        if self.converter.model.float_cost:
            self.distance = self.converter.model.add_float_table(
                self.converter.edge_data["distance"][0]
            )
            if self.aggregation == "max":
                self.partial_cost = self.converter.model.add_float_resource_var(
                    target=0, less_is_better=True
                )
        else:
            self.distance = self.converter.model.add_int_table(
                self.converter.edge_data["distance"][0]
            )
            if self.aggregation == "max":
                self.partial_cost = self.converter.model.add_int_resource_var(
                    target=0, less_is_better=True
                )

    def define_transition_cost(self, location, j, type, transition, single_depot):
        match self.aggregation:
            case "max":
                match type:
                    case "visit_via_depot":
                        if self.converter.model.float_cost:
                            transition.cost = dp.max(
                                dp.FloatExpr.state_cost(),
                                dp.max(
                                    self.partial_cost
                                    + self.distance[
                                        location, self.converter.node_data["depots"][-1]
                                    ],
                                    self.distance[self.converter.node_data["depots"][-1], j],
                                ),
                            )
                        else:
                            transition.cost = dp.max(
                                dp.IntExpr.state_cost(),
                                dp.max(
                                    self.partial_cost
                                    + self.distance[
                                        location, self.converter.node_data["depots"][-1]
                                    ],
                                    self.distance[self.converter.node_data["depots"][-1], j],
                                ),
                            )
                        transition.add_effect(
                            self.partial_cost,
                            self.distance[self.converter.node_data["depots"][-1], j],
                        )
                    case "start_path":
                        pass
                    case _:
                        if self.converter.model.float_cost:
                            transition.cost = dp.max(
                                self.partial_cost + self.distance[location, j],
                                dp.FloatExpr.state_cost(),
                            )
                        else:
                            transition.cost = dp.max(
                                self.partial_cost + self.distance[location, j],
                                dp.IntExpr.state_cost(),
                            )
                        transition.add_effect(
                            self.partial_cost, self.partial_cost + self.distance[location, j]
                        )
            case _:
                match type:
                    case "visit_via_depot":
                        if self.converter.model.float_cost:
                            transition.cost = (
                                self.distance[location, self.converter.node_data["depots"][-1]]
                                + self.distance[self.converter.node_data["depots"][-1], j]
                                + dp.FloatExpr.state_cost()
                            )
                        else:
                            transition.cost = (
                                self.distance[location, self.converter.node_data["depots"][-1]]
                                + self.distance[self.converter.node_data["depots"][-1], j]
                                + dp.IntExpr.state_cost()
                            )
                    case "start_path":
                        pass
                    case _:
                        if self.converter.model.float_cost:
                            transition.cost = self.distance[location, j] + dp.FloatExpr.state_cost()
                        else:
                            transition.cost = self.distance[location, j] + dp.IntExpr.state_cost()

    def define_dual_bounds(self, must_visit):
        match self.aggregation:
            case "sum":
                connections = self.converter.edge_data["connections"]
                distance, type = self.converter.edge_data["distance"]
                nodes = len(self.converter.nodes)
                bounds = []

                if connections is not None:
                    if type:
                        min_distance_to = self.converter.model.add_int_table(
                            [
                                min(
                                    distance[k][j]
                                    for k in range(nodes)
                                    if j != k and connections[k][j]
                                )
                                for j in range(nodes)
                            ]
                        )

                        min_distance_from = self.converter.model.add_int_table(
                            [
                                min(
                                    distance[j][k]
                                    for k in range(nodes)
                                    if j != k and connections[j][k]
                                )
                                for j in range(nodes)
                            ]
                        )
                    else:
                        min_distance_to = self.converter.model.add_float_table(
                            [
                                min(
                                    distance[k][j]
                                    for k in range(nodes)
                                    if j != k and connections[k][j]
                                )
                                for j in range(nodes)
                            ]
                        )

                        min_distance_from = self.converter.model.add_float_table(
                            [
                                min(
                                    distance[j][k]
                                    for k in range(nodes)
                                    if j != k and connections[j][k]
                                )
                                for j in range(nodes)
                            ]
                        )

                else:
                    if type:
                        min_distance_to = self.converter.model.add_int_table(
                            [
                                min(distance[k][j] for k in range(nodes) if j != k)
                                for j in range(nodes)
                            ]
                        )

                        min_distance_from = self.converter.model.add_int_table(
                            [
                                min(distance[j][k] for k in range(nodes) if j != k)
                                for j in range(nodes)
                            ]
                        )
                    else:
                        min_distance_to = self.converter.model.add_float_table(
                            [
                                min(distance[k][j] for k in range(nodes) if j != k)
                                for j in range(nodes)
                            ]
                        )

                        min_distance_from = self.converter.model.add_float_table(
                            [
                                min(distance[j][k] for k in range(nodes) if j != k)
                                for j in range(nodes)
                            ]
                        )

                bounds.append(
                    min_distance_to[must_visit]
                    + (
                        self.structure.location != self.converter.node_data["depots"][-1]
                    ).if_then_else(min_distance_to[self.converter.node_data["depots"][-1]], 0)
                )
                bounds.append(
                    min_distance_from[must_visit]
                    + (
                        self.structure.location != self.converter.node_data["depots"][-1]
                    ).if_then_else(min_distance_from[self.structure.location], 0)
                )

                for b in bounds:
                    self.converter.model.add_dual_bound(b)

                return bounds
            case _:
                return []


class TimeManager:
    def __init__(self, converter, aggregation):
        self.converter = converter
        self.structure = converter.structure
        self.aggregation = aggregation

    def set_objective(self):
        if self.converter.model.float_cost:
            self.time = self.converter.model.add_float_table(self.converter.edge_data["time"][0])
            if self.aggregation == "max":
                self.partial_cost = self.converter.model.add_float_resource_var(
                    target=0, less_is_better=True
                )
        else:
            self.time = self.converter.model.add_int_table(self.converter.edge_data["time"][0])
            if self.aggregation == "max":
                self.partial_cost = self.converter.model.add_int_resource_var(
                    target=0, less_is_better=True
                )

    def define_transition_cost(self, location, j, type, transition, single_depot):
        match self.aggregation:
            case "max":
                match type:
                    case "visit_via_depot":
                        if self.converter.model.float_cost:
                            transition.cost = dp.max(
                                dp.FloatExpr.state_cost(),
                                dp.max(
                                    self.partial_cost
                                    + self.time[location, self.converter.node_data["depots"][-1]],
                                    self.tim[self.converter.node_data["depots"][-1], j],
                                ),
                            )
                        else:
                            transition.cost = dp.max(
                                dp.IntExpr.state_cost(),
                                dp.max(
                                    self.partial_cost
                                    + self.time[location, self.converter.node_data["depots"][-1]],
                                    self.time[self.converter.node_data["depots"][-1], j],
                                ),
                            )
                        transition.add_effect(
                            self.partial_cost, self.time[self.converter.node_data["depots"][-1], j]
                        )
                    case "start_path":
                        pass
                    case _:
                        if self.converter.model.float_cost:
                            transition.cost = dp.max(
                                self.partial_cost + self.time[location, j],
                                dp.FloatExpr.state_cost(),
                            )
                        else:
                            transition.cost = dp.max(
                                self.partial_cost + self.time[location, j], dp.IntExpr.state_cost()
                            )
                        transition.add_effect(
                            self.partial_cost, self.partial_cost + self.time[location, j]
                        )
            case _:
                match type:
                    case "visit_via_depot":
                        if self.converter.model.float_cost:
                            transition.cost = (
                                self.time[location, self.converter.node_data["depots"][-1]]
                                + self.time[self.converter.node_data["depots"][-1], j]
                                + dp.FloatExpr.state_cost()
                            )
                        else:
                            transition.cost = (
                                self.time[location, self.converter.node_data["depots"][-1]]
                                + self.time[self.converter.node_data["depots"][-1], j]
                                + dp.IntExpr.state_cost()
                            )
                    case "start_path":
                        pass
                    case _:
                        if self.converter.model.float_cost:
                            transition.cost = self.time[location, j] + dp.FloatExpr.state_cost()
                        else:
                            transition.cost = self.time[location, j] + dp.IntExpr.state_cost()

    def define_dual_bounds(self, must_visit):
        match self.aggregation:
            case "sum":
                connections = self.converter.edge_data["connections"]
                time, type = self.converter.edge_data["time"]
                nodes = len(self.converter.nodes)
                bounds = []

                if connections is not None:
                    if type:
                        min_time_to = self.converter.model.add_int_table(
                            [
                                min(
                                    time[k][j] for k in range(nodes) if j != k and connections[k][j]
                                )
                                for j in range(nodes)
                            ]
                        )

                        min_time_from = self.converter.model.add_int_table(
                            [
                                min(
                                    time[j][k] for k in range(nodes) if j != k and connections[j][k]
                                )
                                for j in range(nodes)
                            ]
                        )
                    else:
                        min_time_to = self.converter.model.add_float_table(
                            [
                                min(
                                    time[k][j] for k in range(nodes) if j != k and connections[k][j]
                                )
                                for j in range(nodes)
                            ]
                        )

                        min_time_from = self.converter.model.add_float_table(
                            [
                                min(
                                    time[j][k] for k in range(nodes) if j != k and connections[j][k]
                                )
                                for j in range(nodes)
                            ]
                        )

                else:
                    if type:
                        min_time_to = self.converter.model.add_int_table(
                            [min(time[k][j] for k in range(nodes) if j != k) for j in range(nodes)]
                        )

                        min_time_from = self.converter.model.add_int_table(
                            [min(time[j][k] for k in range(nodes) if j != k) for j in range(nodes)]
                        )
                    else:
                        min_time_to = self.converter.model.add_float_table(
                            [min(time[k][j] for k in range(nodes) if j != k) for j in range(nodes)]
                        )

                        min_time_from = self.converter.model.add_float_table(
                            [min(time[j][k] for k in range(nodes) if j != k) for j in range(nodes)]
                        )

                bounds.append(
                    min_time_to[must_visit]
                    + (
                        self.structure.location != self.converter.node_data["depots"][-1]
                    ).if_then_else(min_time_to[self.converter.node_data["depots"][-1]], 0)
                )
                bounds.append(
                    min_time_from[must_visit]
                    + (
                        self.structure.location != self.converter.node_data["depots"][-1]
                    ).if_then_else(min_time_from[self.structure.location], 0)
                )

                for b in bounds:
                    self.converter.model.add_dual_bound(b)

                return bounds
            case _:
                return []


class VehiclesManager:
    def __init__(self, converter):
        self.converter = converter
        self.structure = converter.structure

    def set_objective(self, _):
        pass

    def define_transition_cost(self, location, j, type, transition, single_depot):
        if type == "visit" and single_depot:
            depot = self.converter.node_data["depots"][-1]
            transition.cost = (location == depot).if_then_else(
                dp.IntExpr.state_cost() + 1, dp.IntExpr.state_cost()
            )
        elif type in ["visit_via_depot", "start"]:
            transition.cost = dp.IntExpr.state_cost() + 1

    def define_dual_bounds(self, _):
        pass
