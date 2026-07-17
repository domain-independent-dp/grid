Quickstart
==========

Installation
------------

GRID can be installed from source:

.. code-block:: bash

   git clone https://github.com/domain-independent-dp/grid.git
   cd grid
   pip install -e .

A first model
-------------

The Capacitated Vehicle Routing Problem (CVRP) asks for a set of routes,
each performed by one vehicle starting and ending at a common depot, that
together visit every customer exactly once while respecting a per-vehicle
capacity, minimising the total travel distance. Each customer has a
demand, and the sum of demands along any route cannot exceed the vehicle
capacity.

The following is a complete CVRP instance with a depot, three customers,
two vehicles of capacity 10, and a fully connected graph with symmetric
distances.

.. code-block:: python

   import grid

   demands = {1: 3, 2: 5, 3: 2}
   distances = {
       (0, 1): 4, (0, 2): 6, (0, 3): 5,
       (1, 2): 3, (1, 3): 7, (2, 3): 4,
   }
   distances.update({(j, i): d for (i, j), d in distances.items()})

   model = grid.RoutingModel()

   model.add_vehicle_type(id=0, count=2, capacity=10)
   model.add_node(id=0, depot=True)
   for customer, demand in demands.items():
       model.add_node(id=customer, demand=demand)

   for (i, j), d in distances.items():
       model.add_edge(
           node_from=model.get_node(i),
           node_to=model.get_node(j),
           distance=d,
       )

   model.set_objective(metric="distance")

   result = model.solve(solver="CABS", time_limit=10)

   print(f"Optimal: {result['Optimal']}")
   print(f"Cost:    {result['Cost']}")
   print(f"Routes:  {result['Solution']}")

Step by step
------------

* :class:`~grid.RoutingModel` is the top-level container of the model.
* :meth:`~grid.RoutingModel.add_vehicle_type` registers a homogeneous fleet
  with the given count and capacity.
* :meth:`~grid.RoutingModel.add_node` adds a vertex of the routing graph,
  marked as a depot or carrying a customer demand.
* :meth:`~grid.RoutingModel.add_edge` adds a directed arc with a travel
  attribute (here, ``distance``).
* :meth:`~grid.RoutingModel.set_objective` selects a built-in objective
  metric.
* :meth:`~grid.RoutingModel.solve` compiles the model to DIDP and runs the
  chosen solver, returning a dictionary with the optimality status, the
  cost, the best dual bound, and the routes.

Next steps
----------

* :doc:`modelling-elements` introduces the four core classes and their
  relationships.
* :doc:`native-features` describes the predefined modelling primitives that
  cover common VRP variants (CVRP, VRPTW, PDPTW, ...) and walks through a
  full PDPTW example.
* :doc:`custom-features` shows how to declare user-defined variables and
  expressions for variants that go beyond the native primitives, with a
  full Electric Capacitated VRP (ECVRP) example.
* :doc:`api-reference` provides the complete Python API reference.