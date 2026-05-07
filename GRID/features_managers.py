import didppy as dp
import copy

class ConnectionsManager():

    def __init__(self, converter, connections):
        self.converter = converter
        self.connected = connections

    def expand_model(self, _):
        self.connected = self.converter.model.add_bool_table(self.connected)

    def manage_transition(self, transition, location, j, type):
        match type:
            case "visit" | "return" | "change_vehicle":
                transition.add_precondition(self.connected[location, j])
        
    def manage_state_constraints(self, must_visit, mandatory_nodes):
        pass


class DemandsManager():

    def __init__(self, converter, demands_dict, demands_types, capacities_dict, capacities_types, vehicles_info):
        self.converter = converter
        self.structure = self.converter.structure
        self.vehicles_info = vehicles_info
        self.demands, self.types, self.capacities, self.multiple = self._manage_demand(demands_dict, demands_types, capacities_dict, capacities_types)
        self.number = len(self.demands)
        
    
    def expand_model(self, _):
        if self.multiple:
            tables = []
            capacities = []
            self.loads = []
            for i, demand in enumerate(self.demands):
                if self.types[i]:
                    tables.append(self.converter.model.add_int_table(demand))
                    if self.vehicles_info == "multi_types":
                        capacities.append(self.converter.model.add_int_table(self.capacities[i]))
                        self.vehicles_indexing = self.structure.vehicles_index
                    self.loads.append(self.converter.model.add_int_resource_var(target=0, less_is_better=True))
                else:
                    tables.append(self.converter.model.add_float_table(demand))
                    if self.vehicles_info == "multi_types":
                        capacities.append(self.converter.model.add_float_table(self.capacities[i]))
                        self.vehicles_indexing = self.structure.vehicles_index
                    self.loads.append(self.converter.model.add_float_resource_var(target=0, less_is_better=True))
            self.demands = tables
            if self.vehicles_info == "multi_types":
                self.capacities = capacities 
        else:
            if self.types:
                table = self.converter.model.add_int_table(self.demands)
                if self.vehicles_info == "multi_types":
                    capacities = self.converter.model.add_int_table(self.capacities)
                    self.vehicles_indexing = self.structure.vehicles_index
                self.load = self.converter.model.add_int_resource_var(target=0, less_is_better=True)
            else:
                table = self.converter.model.add_float_table(demand)
                if self.vehicles_info == "multi_types":
                    capacities = self.converter.model.add_float_table(self.capacities)
                    self.vehicles_indexing = self.structure.vehicles_index
                    self.load = self.converter.model.add_float_resource_var(target=0, less_is_better=True)
            self.demands = table
            if self.vehicles_info == "multi_types":
                self.capacities = capacities 
      

    def _manage_demand(self, demands_dict, demands_types, capacities_dict, capacities_types):
        if isinstance(demands_dict, dict):
            ordered_capacities = []
            ordered_types = []
            for key in demands_dict.keys():
                if self.vehicles_info != "multi_types":
                    ordered_capacities.append(capacities_dict[key][0])  
                else:
                    ordered_capacities.append(capacities_dict[key]) 
                ordered_types.append(demands_types[key] and capacities_types[key])
            
            return [row for row in demands_dict.values()], ordered_types, ordered_capacities, True
        else:
            return demands_dict, demands_types, capacities_dict[0], False
        
    
    def manage_transition(self, transition, location, j, type):
        match type:
            case "visit":
                if self.multiple:
                    for i in range(self.number):
                        if self.vehicles_info != "multi_types":
                            transition.add_precondition(self.loads[i] + self.demands[i][j] <= self.capacities[i])
                        else:
                            vehicle_index = self.vehicles_indexing[self.structure.vehicles]
                            transition.add_precondition(self.loads[i] + self.demands[i][j] <= self.capacities[i][vehicle_index])
                        transition.add_effect(self.loads[i], self.loads[i] + self.demands[i][j])
                else:
                    if self.vehicles_info != "multi_types":
                        transition.add_precondition(self.load + self.demands[j] <= self.capacities)
                    else:
                        vehicle_index = self.vehicles_indexing[self.structure.vehicles]
                        transition.add_precondition(self.load + self.demands[j] <= self.capacities[vehicle_index])
                    transition.add_effect(self.load, self.load + self.demands[j])
            case "change_vehicle":
                if self.multiple:
                    for i in range(self.number):
                        transition.add_effect(self.loads[i], 0)
                else:
                    transition.add_effect(self.load, 0)
                             
    def manage_state_constraints(self, must_visit, mandatory_nodes):
        if self.multiple:
            for i in range(self.number):
                total_demand = self.demands[i][mandatory_nodes]
                if self.vehicles_info == "single_type":
                    total_vehicles = len(self.converter.vehicle_data["vehicles"])
                    self.converter.model.add_state_constr((total_vehicles - self.structure.vehicles) * self.capacities[i] - self.loads[i] >= total_demand)
                elif self.vehicles_info == "multi_types":
                    remaining_capacity = 0
                    for v in range(len(self.converter.vehicle_data["vehicles"])):
                        remaining_capacity = remaining_capacity + (v>=self.structure.vehicles).if_then_else(self.capacities[i][self.vehicles_indexing[v]], 0)
                    self.converter.model.add_state_constr(remaining_capacity - self.loads[i] >= total_demand)
                else:
                    self.converter.model.add_state_constr(self.capacities[i] - self.loads[i] >= total_demand)
        else:
            total_demand = self.demands[mandatory_nodes]
            if self.vehicles_info == "single_type":
                total_vehicles = len(self.converter.vehicle_data["vehicles"])
                self.converter.model.add_state_constr((total_vehicles - self.structure.vehicles) * self.capacities - self.load >= total_demand)
            elif self.vehicles_info == "multi_types":
                remaining_capacity = 0
                for v in range(len(self.converter.vehicle_data["vehicles"])):
                    remaining_capacity = remaining_capacity + (v>=self.structure.vehicles).if_then_else(self.capacities[self.vehicles_indexing[v]], 0)
                self.converter.model.add_state_constr(remaining_capacity - self.load >= total_demand)
            else:
                self.converter.model.add_state_constr(self.capacities - self.load >= total_demand)

class TimeWindowsManager():

    def __init__(self, converter, starting_times, ending_times, service_times, waiting_times, time_cost, shortest_cost, times_type, vehicles_info, use_distance, triangular_inequality):
        self.converter = converter
        self.structure = converter.structure
        self.starting_times = starting_times
        self.ending_times = ending_times
        self.service_times = service_times
        self.waiting_times = waiting_times
        self.time_cost = time_cost
        self.shortest_cost = shortest_cost
        self.times_type = times_type
        self.vehicles_info = vehicles_info
        self.use_distance = use_distance
        self.triangular_inequality = triangular_inequality

    def expand_model(self, t):
        if t is not None:
            self.time_cost = t
        else:
            if self.times_type:
                self.time_cost = self.converter.model.add_int_table(self.time_cost)
                self.time = self.converter.model.add_int_resource_var(target = 0, less_is_better = True)
            else:
                self.time_cost = self.converter.model.add_float_table(self.time_cost)
                self.time = self.converter.model.add_float_resource_var(target = 0, less_is_better = True)
        if self.times_type:
            self.time = self.converter.model.add_int_resource_var(target = 0, less_is_better = True)
            self.service_times_table = self.converter.model.add_int_table(self.service_times)
        else:
            self.time = self.converter.model.add_float_resource_var(target = 0, less_is_better = True)
            self.service_times_table = self.converter.model.add_float_table(self.service_times)
            

    def manage_transition(self, transition, location, j, type):
        start = self.starting_times[j]
        end = self.ending_times[j]
        service = self.service_times_table[location] if self.service_times is not None else None
        wait = self.waiting_times[j] if self.waiting_times is not None else None
        if service is not None:
            moving_time = self.time + service + self.time_cost[location, j]
        else:
            moving_time = self.time + self.time_cost[location, j]
        match type:
            case "visit":
                if end is not None:
                    transition.add_precondition(moving_time <= end)
                if start is not None:
                    if wait is not None:
                        transition.add_precondition(moving_time + wait >= start)
                    transition.add_effect(self.time, dp.max(moving_time, start))
                else:
                    transition.add_effect(self.time, moving_time)
            case "return":
                if end is not None:
                    transition.add_precondition(moving_time <= end)
                transition.add_effect(self.time, moving_time)
            case "change_vehicle":
                if end is not None:
                    transition.add_precondition(moving_time <= end)
                transition.add_effect(self.time, 0)

    def manage_state_constraints(self, must_visit, mandatory_nodes):
        if self.shortest_cost is not None:
            if self.times_type:
                shortest_distance = self.converter.model.add_int_table(self.shortest_cost)
            else:                
                shortest_distance = self.converter.model.add_float_table(self.shortest_cost)
        else:

            if not self.triangular_inequality or self.converter.edge_data["connections"] is not None:
                if self.use_distance:
                    time_matrix = self.converter.edge_data["distance"][0]
                else:
                    time_matrix = self.converter.edge_data["time"][0]
                connections = self.converter.edge_data["connections"]
                shortest_distance_matrix = copy.deepcopy(time_matrix)
                ub = max(self.ending_times) - min(self.starting_times) + 1
                n = len(self.converter.nodes)

                for i in range(n):
                    for j in range(n):
                        if connections[i][j]:
                            shortest_distance_matrix[i][j] += self.service_times[i]
                        else:
                            shortest_distance_matrix[i][j] = ub
                for k in range(n):
                    for i in range(n):
                        for j in range(n):
                            if shortest_distance_matrix[i][j] > shortest_distance_matrix[i][k] + shortest_distance_matrix[k][j]:
                                shortest_distance_matrix[i][j] = shortest_distance_matrix[i][k] + shortest_distance_matrix[k][j]
                if self.times_type:
                    shortest_distance = self.converter.model.add_int_table(shortest_distance_matrix)
                else:                
                    shortest_distance = self.converter.model.add_float_table(shortest_distance_matrix)

            else:
                shortest_distance = self.time_cost

        if self.vehicles_info == "tsp":
            for j in self.converter.node_data["customers"]:
                end = self.ending_times[j]
                if end is not None:
                    self.converter.model.add_state_constr(
                        ~mandatory_nodes.contains(j) | (self.time + shortest_distance[self.structure.location, j] <= end)
                    )

        elif must_visit is not None:
            for j in self.converter.node_data["customers"]:
                end = self.ending_times[j]
                if end is not None:
                    self.converter.model.add_state_constr(
                        ~must_visit.contains(j) | (self.time + shortest_distance[self.structure.location, j] <= end)
                    )
            depot = self.converter.node_data["depots"][-1]
            depot_end = self.ending_times[depot]
            if depot_end is not None:
                self.converter.model.add_state_constr(
                    self.time + shortest_distance[self.structure.location, depot] <= depot_end
                )
        
        else:
            depot = self.converter.node_data["depots"][-1]
            depot_end = self.ending_times[depot]
            if depot_end is not None:
                self.converter.model.add_state_constr(
                    self.time + shortest_distance[self.structure.location, depot] <= depot_end
                )
    

class PickUpAndDeliveryManager():

    def __init__(self, converter, commodities_dict, commodities_type, pd_capacities, pd_type, vehicles_info):
        self.converter = converter
        self.structure = self.converter.structure
        self.commodities = commodities_dict
        self.commodities_type = commodities_type and pd_type
        self.pd_capacities = pd_capacities
        self.vehicles_info = vehicles_info
        self.split, self.deltas, self.predecessors, self.successors = self._manage_commodities(commodities_dict)
               
    def expand_model(self, _):
        self.didp_vars = {}
        if self.common_var:
            if self.commodities_type:
                self.didp_vars["Common"] = self.converter.model.add_int_resource_var(target=0, less_is_better=True)
            else:
                self.didp_vars["Common"] = self.converter.model.add_float_resource_var(target=0, less_is_better=True)
        for key in self.split["M-M"]:
            if self.commodities_type:
                self.didp_vars[key] = self.converter.model.add_int_resource_var(target=0, less_is_better=True)
            else:
                self.didp_vars[key] = self.converter.model.add_float_resource_var(target=0, less_is_better=True)
        if self.vehicles_info == "multi_types":
            self.vehicles_indexing = self.structure.vehicles_index
            if self.commodities_type:
                self.pd_capacities = self.converter.model.add_int_table(self.pd_capacities)
            else:
                self.pd_capacities = self.converter.model.add_float_table(self.pd_capacities)
        self.predecessors_table = self.converter.model.add_set_table(self.predecessors, object_type=self.structure.customer)
        if self.successors is not None:
            self.must_visit = self.converter.model.add_set_var(target = [], object_type = self.structure.customer)
            self.successors_table = self.converter.model.add_set_table(self.successors, object_type=self.structure.customer)
    
    def _manage_split(self, total_commodities):
        split = {
            "1-1": [],
            "M-M": [],
            "1-M": [],
            "M-1": [],
        }
        for key in total_commodities.keys():
            if len(total_commodities[key]["pickup"]) > 1:
                if len(total_commodities[key]["delivery"]) > 1:
                        split["M-M"].append(key)
                else:
                        split["M-1"].append(key)
            else:
                if len(total_commodities[key]["delivery"]) > 1:
                        split["1-M"].append(key)
                else:
                        split["1-1"].append(key)
        return split

    def _manage_commodities(self, commodities_dict):
        split = self._manage_split(commodities_dict)
        deltas = {}
        predecessors = [set() for _ in range(len(self.converter.nodes))]
        successors = [set() for _ in range(len(self.converter.nodes))] if self.vehicles_info != "tsp" else None
        self.common_var = len(split["1-1"]) + len(split["M-1"]) + len(split["1-M"]) > 0
        if self.common_var:
            deltas["Common"] = [0 for _ in range(len(self.converter.nodes))] 
        
        for key in split["1-1"]:
            pickup_node, pickup_value = commodities_dict[key]["pickup"][0]
            delivery_node, delivery_value = commodities_dict[key]["delivery"][0]
            deltas["Common"][pickup_node] += abs(pickup_value)
            deltas["Common"][delivery_node] -= abs(delivery_value)
            predecessors[delivery_node].add(pickup_node)
            if self.vehicles_info != "tsp":
                successors[pickup_node].add(delivery_node)

        for key in split["1-M"]:
            pickup_node, pickup_value = commodities_dict[key]["pickup"][0]
            deltas["Common"][pickup_node] += abs(pickup_value)
            for delivery_node, delivery_value in commodities_dict[key]["delivery"]:
                deltas["Common"][delivery_node] -= abs(delivery_value)
                predecessors[delivery_node].add(pickup_node)
                if self.vehicles_info != "tsp":
                    successors[pickup_node].add(delivery_node)
        
        for key in split["M-1"]:
            delivery_node, delivery_value = commodities_dict[key]["delivery"][0]
            deltas["Common"][delivery_node] -= abs(delivery_value)
            for pickup_node, pickup_value in commodities_dict[key]["pickup"]:
                deltas["Common"][pickup_node] += abs(pickup_value)
                predecessors[delivery_node].add(pickup_node)
                if self.vehicles_info != "tsp":
                    successors[pickup_node].add(delivery_node)

        for key in split["M-M"]:
            deltas[key] = [0 for _ in range(len(self.converter.nodes))]
            for pickup_node, pickup_value in commodities_dict[key]["pickup"]:
                deltas[key][pickup_node] += abs(pickup_value)
            for delivery_node, delivery_value in commodities_dict[key]["delivery"]:
                deltas[key][delivery_node] -= abs(delivery_value)
        
        return split, deltas, predecessors, successors
    
    def manage_transition(self, transition, location, j, type):
        if self.vehicles_info != "multi_types":
            capacity = self.pd_capacities[0] 
        else:
            vehicle_index = self.vehicles_indexing[self.structure.vehicles]
            capacity = self.pd_capacities[vehicle_index]
        match type:
            case "visit":
                total_load = 0
                capacity_prec = False
                if self.common_var:
                    if self.deltas["Common"][j] != 0:
                        capacity_prec = self.deltas["Common"][j] > 0
                        total_load += self.didp_vars["Common"] + self.deltas["Common"][j]
                        transition.add_effect(self.didp_vars["Common"], self.didp_vars["Common"] + self.deltas["Common"][j])
                    if self.successors is not None:
                        if len(self.successors[j]) > 0:
                            transition.add_effect(self.must_visit, self.must_visit.union(self.successors_table[j]).remove(j))
                        else:
                            transition.add_effect(self.must_visit, self.must_visit.remove(j))
                    if len(self.predecessors[j])>0:
                        transition.add_precondition(self.structure.unvisited.isdisjoint(self.predecessors_table[j]))
                for key in self.split["M-M"]:
                    if self.deltas[key][j] != 0:
                        capacity_prec = True
                        total_load += self.didp_vars[key] + self.deltas[key][j]
                        transition.add_effect(self.didp_vars[key], self.didp_vars[key] + self.deltas[key][j])
                        transition.add_precondition(self.didp_vars[key] + self.deltas[key][j] >= 0)
                if capacity_prec:
                    transition.add_precondition(total_load <= capacity)

            case "change_vehicle":
                if self.common_var:
                    if self.successors is not None:
                        transition.add_precondition(self.must_visit.is_empty())
                for key in self.split["M-M"]:
                    transition.add_precondition(self.didp_vars[key] == 0)
        

    def manage_state_constraints(self, must_visit, mandatory_nodes):
        pass


class VisitManager():

    def __init__(self, converter, optional_nodes, multiple_visits):
        self.converter = converter
        self.structure = converter.structure
        self.optional_nodes = optional_nodes if optional_nodes is not None else []
        self.multiple_visits = multiple_visits if multiple_visits is not None else {}

    def expand_model(self, _):
        customers = self.converter.node_data["customers"]
        if self.optional_nodes:
            self.optional_nodes_set = self.converter.model.create_set_const(object_type = self.structure.customer, value=self.optional_nodes)
        if self.multiple_visits:
            self.multiple_visits_limits = {}
            for i,value in self.multiple_visits.items():
                if value is not None:
                    self.multiple_visits_limits[i] = self.converter.model.add_int_var(target=value)
                else:
                    self.multiple_visits_limits[i] = value
        self.unvisited = self.converter.model.add_set_var(object_type=self.structure.customer, target=[c for c in customers if not (c in self.multiple_visits.keys() and c in self.optional_nodes)]) 

    def get_mandatory_nodes(self):
        if self.optional_nodes and set(self.optional_nodes) != set(self.multiple_visits.keys()):
            return self.unvisited.difference(self.optional_nodes_set)
        else:
            return self.unvisited
            
    def manage_transition(self, transition, location, j, type):
        connections = self.converter.edge_data["connections"]
        match type:
            case "visit":
                if j in self.multiple_visits:
                    if connections is None:
                        transition.add_precondition(location != j)
                    var = self.multiple_visits_limits[j]
                    if var is not None:
                        transition.add_precondition(self.multiple_visits_limits[j] > 0)
                        transition.add_effect(self.multiple_visits_limits[j], self.multiple_visits_limits[j] - 1)
                else:
                    transition.add_precondition(self.unvisited.contains(j))
                if not (j in self.multiple_visits and j in self.optional_nodes):
                    transition.add_effect(self.unvisited, self.unvisited.remove(j))
        
    def manage_state_constraints(self, must_visit, mandatory_nodes):
        pass
            
        



        
    
        


  


