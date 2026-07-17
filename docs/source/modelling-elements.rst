Modelling Elements
==================

GRID describes a routing problem on a directed graph :math:`G = (N, E)`
through four core classes. Together they define the graph structure, the
fleet, the configurable attributes, and the entry point for compilation
and solving.

:class:`~grid.RoutingModel`
   The top-level container. Owns the graph, the registered vehicle types,
   the global user-defined variables and constraints, and the objective.
   Compiled to a DIDP model upon :meth:`~grid.RoutingModel.solve`.

:class:`~grid.Node`
   A vertex of the graph (:math:`N`). Represents a customer, a depot, or
   any other location involved in a route. Carries attributes for native
   features (demand, time window, service time, pickup/delivery, etc.)
   and accepts user-attached transitions and constraints.

:class:`~grid.Edge`
   A directed arc of the graph (:math:`E`) connecting two nodes. Carries
   travel attributes (distance, travel time, per-vehicle variable cost)
   and accepts user-attached transitions and constraints.

:class:`~grid.VehicleType`
   A homogeneous group of identical vehicles. Carries fleet-level
   attributes (count, capacity, range and time limits, permitted depots,
   fixed cost) and is the scope on which user-defined variables are
   declared.

Building a model
----------------

Nodes, edges, and vehicle types are created through methods of
:class:`~grid.RoutingModel`:

.. code-block:: python

   import grid

   model = grid.RoutingModel()

   depot = model.add_node(id=0, depot=True)
   customer = model.add_node(id=1, demand=3)
   model.add_edge(node_from=depot, node_to=customer, distance=4)
   model.add_vehicle_type(id=0, count=2, capacity=10)

Each ``add_*`` method returns the created entity, which can be stored in
a variable for later reference. Entities can also be retrieved by id
through :meth:`~grid.RoutingModel.get_node`,
:meth:`~grid.RoutingModel.get_edge`,
:meth:`~grid.RoutingModel.get_vehicle_type`, and the corresponding
:meth:`~grid.RoutingModel.get_nodes`,
:meth:`~grid.RoutingModel.get_edges`,
:meth:`~grid.RoutingModel.get_vehicle_types` methods that return sorted
lists of all registered entities.

The global objective is configured via
:meth:`~grid.RoutingModel.set_objective`, and the model is solved via
:meth:`~grid.RoutingModel.solve`, which returns a dictionary with the
cost, the routes, optimality and feasibility flags, and the best dual
bound.

Modelling features
------------------

Routing requirements are configured through two complementary mechanisms:

* :doc:`native-features` describes the predefined attributes that
  configure the four classes above (e.g. ``demand`` on a node,
  ``capacity`` on a vehicle type) and the built-in objective metrics.
  Many common VRP variants (CVRP, VRPTW, PDPTW) can be modelled with
  these alone.

* :doc:`custom-features` describes the mechanism for going beyond native
  attributes: user-defined variables declared on a vehicle type, and
  expressions attached to nodes or edges as preconditions or variable
  updates. Most non-trivial variants combine native and custom features.