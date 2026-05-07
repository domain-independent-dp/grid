import didppy as dp
from .features_managers import *
from .structure_managers import *
from .expressions_manager import ExpressionsManager
from .objective_managers import *
from .expressions import *
import re, math

def _manage_numbers(x):
    if x is None:
        return None
    float_x = float(x)
    if float_x.is_integer():
        return int(float_x)
    else:
        return float_x
    
def _int_cost(array):
        is_int = True
        for elem in array:
            if isinstance(elem, (list, np.ndarray)):
                is_int = is_int and _int_cost(elem)
            else:
                elem = _manage_numbers(elem)
                is_int = is_int and isinstance(elem, int)
            if not is_int:
                return False
        return True

def _remove_inf(array, max_value):
    for i in range(len(array)):
        for j in range(len(array[i])):
            if array[i][j] == math.inf:
                array[i][j] = max_value
    return array
    
def _convert_operator(op):
    match op:
        case "plus":
            return dp.FOperator.Plus
        case "product":
            return dp.FOperator.Product
        case "min":
            return dp.FOperator.Min
        case "max":
            return dp.FOperator.Max
        case "overwrite":
            return dp.FOperator.OverWrite

class DIDPConverter():

    def __init__(self, routing_model, maximize=False):
        self.routing_model = routing_model
        self.maximize = maximize
        self.structure, self.vehicles_info = self._extract_structure()

        self.nodes = routing_model.get_nodes()
        self.vehicle_types = routing_model.get_vehicle_types()
        self.edges = routing_model.get_edges()
        
        self.node_data = self._extract_from_nodes()
        self.vehicle_data = self._extract_from_vehicles()
        self.edge_data = self._extract_from_edges()

        self.vehicles_vars = self.vehicle_data["vars"]

        self.model_vars = routing_model.variables

        self.managers = self._init_managers() 

        self.expr_manager = None
        if len(self.model_vars) + len(self.vehicles_vars) > 0:
            self.expr_manager = ExpressionsManager(self, self.vehicles_vars, self.model_vars, self.routing_model.constraints, self.edge_data["updates"], self.edge_data["constraints"], self.node_data["updates"], self.node_data["constraints"], self.vehicles_info)

        self.objective_manager = self._init_objective_manager()

        self.structure.build_model(self.managers, self.objective_manager, self.expr_manager)

    def _init_objective_manager(self):
        obj = self.routing_model.metric
        if obj is None:
            obj = self.routing_model.objective_variables
        if isinstance(obj, Var):
            self.model = dp.Model(float_cost = obj.type == "float", maximize=self.maximize)
            #bounds = []
            #if self.routing_model.operator is not None:
                #bounds = self.routing_model.dual_bounds
            self.expr_manager.set_objective(self.routing_model.aggregation, [], obj)
            return self.expr_manager
        elif isinstance(obj, list):
            is_int = True
            for v in obj:
                is_int = is_int and v.type == "integer"
            self.model = dp.Model(float_cost = not is_int, maximize=self.maximize)
            #bounds = []
            #if self.routing_model.operator is not None:
                #bounds = self.routing_model.dual_bounds
            self.expr_manager.set_objective(self.routing_model.aggregation, [], obj)
            return self.expr_manager
        elif obj == "distance":
            self.model = dp.Model(float_cost = not self.edge_data["distance"][1], maximize=self.maximize)
            return DistanceManager(self, self.routing_model.aggregation)
        elif obj == "time":
            self.model = dp.Model(float_cost = not self.edge_data["time"][1], maximize=self.maximize)
            return TimeManager(self, self.routing_model.aggregation)
        elif obj == "vehicles":
            self.model = dp.Model(float_cost = False, maximize=self.maximize)
            return VehiclesManager(self)

    def _extract_structure(self):
        vehicles_info = None
        structure = None
        if self.routing_model.vehicle_types > 1:
            vehicles_info = "multi_types"
        elif self.routing_model.vehicles_count > 1:
            vehicles_info = "single_type"
        else:
            vehicles_info = "tsp"
        if self.routing_model.depots > 1:
            structure = MultiDepot(self, vehicles_info)
        else:
            structure = SingleDepot(self, vehicles_info)
        return structure, vehicles_info
    
        
    def _extract_from_nodes(self):
        is_demand = False
        total_nodes = len(self.nodes)

        from_node_id_to_idx = {}
        depots_indexing = []
        customers_indexing = []
        optional_indexing = []
        multiple_visits_indexing = {}
        demands_dict = {}
        single_demands = [0 for _ in range(total_nodes)]
        single_demands_int = True
        demands_int = {}
        multiple_demands = False

        is_time = False
        is_optional = False
        is_multiple = False
        times_int = True
        is_service = False
        is_waiting = False
        is_update = False
        is_constraint = False
        is_pd = False
        pd_int = True
        starting_times = []
        ending_times = []
        service_times = []
        waiting_times = []
        updates = []
        constraints = []

        total_commodities = {}

        for i, node in enumerate(self.nodes):
            from_node_id_to_idx[node.id] = i
            if node.depot:
                depots_indexing.append(i)
            else:
                customers_indexing.append(i)

                if node.optional:
                    is_optional = True
                    optional_indexing.append(i)
            
                if node.max_visits != 1:
                    is_multiple = True
                    multiple_visits_indexing[i] = node.max_visits

            if node.demand is not None:
                is_demand = True
                if isinstance(node.demand, dict):
                    multiple_demands = True
                    for d in node.demand.keys():
                        demand = _manage_numbers(node.demand[d])
                        if d not in demands_dict.keys():
                            row = [0 for _ in range(total_nodes)]
                            demands_int[d] = isinstance(demand, int)
                        else:
                            row = demands_dict[d]
                            demands_int[d] = demands_int[d] and isinstance(demand, int)
                        row[i] = demand
                        demands_dict[d] = row
                else:
                    demand = _manage_numbers(node.demand)
                    single_demands[i] = demand
                    single_demands_int = single_demands_int and isinstance(demand, int)

            if node.tw_start is not None or node.tw_end is not None:
                is_time = True
                if node.tw_start is not None:
                    tw_start = _manage_numbers(node.tw_start)
                    times_int = times_int and isinstance(tw_start, int)
                if node.tw_end is not None:
                    tw_end = _manage_numbers(node.tw_end)
                    times_int = times_int and isinstance(tw_end, int)
            starting_times.append(_manage_numbers(node.tw_start))
            ending_times.append(_manage_numbers(node.tw_end))
            if node.service_t is not None:
                is_service = True
                service = _manage_numbers(node.service_t)
                times_int = times_int and isinstance(service, int)
            service_times.append(_manage_numbers(node.service_t))
            if node.waiting_t is not None:
                waiting = _manage_numbers(node.waiting_t)
                is_waiting = True
                times_int = times_int and isinstance(waiting, int)
            waiting_times.append(_manage_numbers(node.service_t))

            if len(node.transitions) > 0:
                is_update = True
                effects = []
                for t in node.transitions:
                    effects.append(t)
                updates.append(effects)
            else:
                updates.append([])

            if len(node.constraints) > 0:
                is_constraint = True
                con = []
                for c in node.constraints:
                    con.append(c)
                constraints.append(con)
            else:
                constraints.append([])

            if node.pickup is not None:
                is_pd = True
                for commodity, value in node.pickup.items():
                    value = _manage_numbers(value)
                    pd_int = pd_int and isinstance(value, int)
                    commodity_dict = total_commodities.get(commodity, {})
                    pickup_list = commodity_dict.get("pickup", [])
                    pickup_list.append((i, value))
                    commodity_dict["pickup"] = pickup_list
                    total_commodities[commodity] = commodity_dict
            if node.delivery is not None:
                for commodity, value in node.delivery.items():
                    value = _manage_numbers(value)
                    pd_int = pd_int and isinstance(value, int)
                    commodity_dict = total_commodities.get(commodity, {})
                    delivery_list = commodity_dict.get("delivery", [])
                    delivery_list.append((i, value))
                    commodity_dict["delivery"] = delivery_list
                    total_commodities[commodity] = commodity_dict
        
        demands_result = None
        if is_demand:
            if multiple_demands:
                demands_result = (demands_dict, demands_int)
            else:
                demands_result = (single_demands, single_demands_int)

        return {
            "from_node_id_to_idx": from_node_id_to_idx,
            "depots" : depots_indexing,
            "customers" : customers_indexing,
            "optional customers": optional_indexing if is_optional else None,
            "multiple visits": multiple_visits_indexing if is_multiple else None,
            "demands" : demands_result if is_demand else None,
            "time_intervals": ([starting_times, ending_times], times_int) if is_time else None,
            "service": service_times if is_service else None,
            "waiting": waiting_times if is_waiting else None,
            "updates": updates if is_update else None,
            "constraints": constraints if is_constraint else None,
            "commodities": (total_commodities, pd_int) if is_pd else None
        }
    
    def _extract_from_vehicles(self):
        vehicles_indexing = []
        capacities_dict = {}
        is_capacity = False
        int_capacity = {}
        is_vars = False
        is_pd = False
        vehicle_vars = {}
        single_capacities = [0 for _ in range(len(self.vehicle_types))]
        multiple_capacities = False
        single_capacities_int = True
        depots = self.node_data["depots"]
        need_skip = len(self.vehicle_types) > 1
        if need_skip:
            skip = []
            shift = 0
        if len(depots) > 1:
            allowed_starts = []
            allowed_ends = []
        for i, vehicle_type in enumerate(self.vehicle_types):
            for _ in range(vehicle_type.count):
                vehicles_indexing.append(i)
            if need_skip:
                if i+1 < len(self.vehicle_types): 
                    skip.append(shift + vehicle_type.count)
                else:
                    skip.append(skip[-1])
                shift += vehicle_type.count  

            if len(depots) > 1:
                start = set()
                end = set()
                if vehicle_type.start_node is None:
                    start.update(depots)
                else:
                    for depot in depots:
                        if vehicle_type.start_node == depot:
                            start.add(depot)
                if vehicle_type.end_node is None:
                    end.update(depots)
                else:
                    for depot in depots:
                        if vehicle_type.end_node == depot:
                            end.add(depot)
                allowed_starts.append(start)
                allowed_ends.append(end)
            

            if vehicle_type.capacity is not None:
                is_capacity = True
                if isinstance(vehicle_type.capacity, dict):
                    multiple_capacities = True
                    for c in vehicle_type.capacity.keys():
                        capacity = _manage_numbers(vehicle_type.capacity[c])
                        if c not in capacities_dict.keys():
                            row = [0 for _ in range(len(self.vehicle_types))]
                            int_capacity[c] = isinstance(capacity, int)
                        else:
                            int_capacity[c] = int_capacity and isinstance(capacity, int)
                            row = capacities_dict[c]
                        row[i] = capacity
                        capacities_dict[c] = row
                else:
                    capacity = _manage_numbers(vehicle_type.capacity)
                    single_capacities[i] = capacity
                    single_capacities_int = single_capacities_int and isinstance(capacity, int)


            if len(vehicle_type.variables) > 0:
                is_vars = True
                for var in vehicle_type.variables:
                    vehicle_vars[var] = i

        capacity_results = None
        if is_capacity:
            if multiple_capacities:
                capacity_results = (capacities_dict, int_capacity)
            else:
                capacity_results = (single_capacities, single_capacities_int)

        return {
            "vehicles": vehicles_indexing,
            "skip": skip if need_skip else None,
            "capacities": capacity_results if is_capacity else None,
            "vars": vehicle_vars if is_vars else {},
            "allowed_starts": allowed_starts if len(depots) > 1 else None,
            "allowed_ends": allowed_ends if len(depots) > 1 else None,
            "pd_capacities": [single_capacities, single_capacities_int] if is_capacity else None
        }
    
    def _extract_from_edges(self):
        is_distance = False
        is_connected = True
        is_update = False
        is_constraint = False
        is_time = False
        int_time = True
        int_distance = True
        total_distance = []
        connections = []
        total_updates = []
        constraints = []
        total_time = []
        max_distance = 0
        max_time = 0
        for node_from in self.nodes:
            distance_row = []
            connection_row = []
            updates_row = []
            constraints_row = []
            time_row = []
            for node_to in self.nodes:
                edge = self.routing_model.get_edge(node_from.id, node_to.id)
                if edge is not None:
                    connection_row.append(True)
                    if edge.distance is not None:
                        distance = _manage_numbers(edge.distance)
                        max_distance = max(max_distance, distance)
                        int_distance = int_distance and isinstance(distance, int)
                        is_distance = True
                        distance_row.append(distance)
                    else:
                        distance_row.append(math.inf)  

                    if edge.travel_time is not None:
                        time = _manage_numbers(edge.travel_time)
                        max_time = max(max_time, time)
                        int_time = int_time and isinstance(time, int)
                        is_time = True
                        time_row.append(edge.travel_time)
                    else:
                        time_row.append(math.inf)

                    if len(edge.transitions) > 0:
                        is_update = True
                        effects = []
                        for t in edge.transitions:
                            effects.append(t)
                        updates_row.append(effects)
                    else:
                        updates_row.append([])

                    if len(edge.constraints) > 0:
                        is_constraint = True
                        con = []
                        for c in edge.constraints:
                            con.append(c)
                        constraints_row.append(con)
                    else:
                        constraints_row.append([])
                        
                else:
                    if node_from.id != node_to.id:
                        is_connected = False  
                    connection_row.append(False)
                    distance_row.append(math.inf)  
                    updates_row.append([])
                    constraints_row.append([])
                    time_row.append(math.inf)
            total_distance.append(distance_row)
            connections.append(connection_row)
            total_updates.append(updates_row)
            constraints.append(constraints_row)
            total_time.append(time_row)
        
        total_distance = _remove_inf(total_distance, max_distance)
        total_time = _remove_inf(total_time, max_distance) 
        return {
            "distance": (total_distance, int_distance) if is_distance else None,
            "connections": connections if not is_connected else None,
            "updates": total_updates if is_update else None,
            "constraints": constraints if is_constraint else None,
            "time": (total_time, int_time) if is_time else None
        }

    
    def _init_managers(self):
        managers = []

        managers.append(VisitManager(self, self.node_data["optional customers"], self.node_data["multiple visits"]))

        connections = self.edge_data["connections"]
        if connections is not None:
            managers.append(ConnectionsManager(self, connections))

        if self.node_data["demands"] is not None:
            managers.append(DemandsManager(self, self.node_data["demands"][0],self.node_data["demands"][1], self.vehicle_data["capacities"][0], self.vehicle_data["capacities"][1], self.vehicles_info))

        if self.node_data["time_intervals"] is not None:
            time_cost = self.edge_data["time"][0] if self.edge_data["time"] is not None else None
            shortest_cost = self.routing_model.shortest_time if self.routing_model.shortest_time is not None else None
            use_distance = time_cost is None
            if use_distance:
                time_cost = self.edge_data["distance"][0]
                shortest_cost = self.routing_model.shortest_distance if self.routing_model.shortest_distance is not None else None
                cost_type = self.edge_data["distance"][1]
            else:
                cost_type = self.edge_data["time"][1]
            starting_times = self.node_data["time_intervals"][0][0]
            ending_times = self.node_data["time_intervals"][0][1]
            times_type = self.node_data["time_intervals"][1]
            service = self.node_data["service"]
            waiting =  self.node_data["waiting"]
            if shortest_cost is not None:
                cost_type = cost_type and _int_cost(shortest_cost)
            managers.append(TimeWindowsManager(self, starting_times, ending_times, service, waiting, time_cost, shortest_cost, times_type and cost_type, self.vehicles_info, use_distance, self.routing_model.triangular_inequality))

        if self.node_data["commodities"] is not None:
            managers.append(PickUpAndDeliveryManager(self, self.node_data["commodities"][0], self.node_data["commodities"][0], self.vehicle_data["pd_capacities"][0], self.vehicle_data["pd_capacities"][1], self.vehicles_info))

        return managers
        
    def build_path(self, solution, depots=None):
            paths = []
            path = []
            vehicles = 1
            for t in solution.transitions:
                print(t.name)
                if depots is None:
                    if "visit" in t.name.lower():
                        match = re.search(r"\d+\.?\d*", t.name) 
                        customer = int(match.group()) if match else None  
                        if "vehicle" in t.name:
                            vehicles +=1
                            paths.append(path)
                            path = []
                        path.append(customer)
                    elif "vehicle" in t.name:
                        vehicles +=1
                        paths.append(path)
                        path = []
                else:
                    match = re.search(r"\d+\.?\d*", t.name)  
                    customer = int(match.group()) if match else None  
                    path.append(customer)
                    if "vehicle" in t.name:
                        vehicles +=1
                        paths.append(path)
                        path = []
            if path:
                paths.append(path)
            print(solution.cost)
            return vehicles, paths
    
    def get_yaml(self):
        return self.model.dump_to_str()
    
    def get_didp_model(self):
        return self.model

    def solve(self, solver_string, time_limit):
        if self.routing_model.operator is not None:
            op = _convert_operator(self.routing_model.operator)
        else:
            op = dp.FOperator.Plus
        solver_map = {
            "LNBS": dp.LNBS,
            "CABS": dp.CABS,
        }
        solver_class = solver_map.get(solver_string.upper())
        solver = solver_class(self.model, time_limit=time_limit, quiet=True, f_operator=op)
        solution = solver.search()
        cost = None
        routes = None
        if solution.cost is not None:
            cost = solution.cost
            _, routes = self.build_path(solution)
        return {
            "Optimal" : solution.is_optimal,
            "Infeasible": solution.is_infeasible,
            "Best Bound": solution.best_bound,
            "Cost": cost,
            "Solution": routes
        }

