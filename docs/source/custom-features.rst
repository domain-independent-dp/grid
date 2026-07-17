Custom Features
===============

When native features (see :doc:`native-features`) are not sufficient,
GRID lets users describe custom behaviour through:

* **User-defined variables** declared on a :class:`~grid.VehicleType` or
  on :class:`~grid.RoutingModel`, representing quantities or sets that
  evolve along a route.
* **Expressions** built over these variables using Python operators and
  the free functions :func:`~grid.max`, :func:`~grid.min`,
  :func:`~grid.sqrt`, :func:`~grid.log`, :func:`~grid.select`, attached
  to nodes, edges, or the model as constraints or transitions.

The sections below describe these in order (declaring, writing,
attaching, and using them in custom objectives), ending with a complete
example for the Electric Capacitated Vehicle Routing Problem (ECVRP).

Declaring variables
-------------------

User-defined variables are declared on a :class:`~grid.VehicleType`. This
choice reflects the role of vehicles as the elements that build solutions
during search: a :class:`~grid.VehicleType` provides the natural scope
for quantities that evolve along a route while remaining shared across
identical vehicles of the same type.

Three methods are available:

:meth:`VehicleType.add_integer_var <grid.VehicleType.add_integer_var>`
   Creates an integer variable with an initial value. An optional
   ``preference`` (``"low"`` or ``"high"``) is a solver hint: if set,
   the user must guarantee that, among two partial routes ending at the
   same node, the route with the preferred value of the variable always
   leads to a better solution.

:meth:`VehicleType.add_float_var <grid.VehicleType.add_float_var>`
   Same as the integer version but for floating-point variables.

:meth:`VehicleType.add_nodes_set_var <grid.VehicleType.add_nodes_set_var>`
   Creates a set variable whose elements are node ids. Useful to keep
   track of subsets of the graph along a route (e.g. unvisited stations,
   served commodities, ...).

The returned objects are :class:`~grid.Var` (integer or float) and
:class:`~grid.SetVar`. They combine with Python operators to build
expression trees.

Global variables can also be declared on :class:`~grid.RoutingModel`
through analogous ``add_*`` methods. These are not tied to any vehicle
type and apply across the whole model.

Writing expressions
-------------------

Expressions are built by combining variables, Python literals, and the
free functions of grid. Python's arithmetic, comparison, and logical
operators are overloaded on :class:`~grid.Var` and :class:`~grid.SetVar`
to produce expression trees with the expected semantics:

.. code-block:: python

   # `load`, `battery` are Var instances obtained from a VehicleType.

   load - 3                    # subtraction, result is an integer expression
   battery - distance * rate   # composition with literals
   load >= 0                   # comparison, result is a boolean expression
   (load > 0) & (battery > 0)  # logical AND, result is a boolean expression

For operations that have no equivalent Python operator, use the free
functions :func:`~grid.max`, :func:`~grid.min`, :func:`~grid.sqrt`,
:func:`~grid.log`, :func:`~grid.select`:

.. code-block:: python

   grid.max([load, 0])           # element-wise max over a list
   grid.sqrt(distance)           # square root
   grid.select(distance_row, j)  # indexing into an array expression

Set variables additionally expose set-algebra methods:
:meth:`~grid.SetVar.add`, :meth:`~grid.SetVar.remove`,
:meth:`~grid.SetVar.contains`, :meth:`~grid.SetVar.is_empty`,
:meth:`~grid.SetVar.len`. Each returns an expression usable in further
operations:

.. code-block:: python

   unv_stations.contains(s)      # boolean: is s currently in the set
   unv_stations.remove(s)        # set expression: set with s removed
   unv_stations.is_empty()       # boolean: is the set empty
   unv_stations.len()            # integer: cardinality of the set

Attaching expressions
---------------------

An expression alone is just a tree of operations. To affect the model,
it must be attached to an entity as either a constraint or a transition.

**Constraints.** Register a boolean precondition that must hold for the
node, edge, or model to remain feasible. They are added via
:meth:`Node.add_constraint <grid.Node.add_constraint>`,
:meth:`Edge.add_constraint <grid.Edge.add_constraint>`, or
:meth:`RoutingModel.add_constraint <grid.RoutingModel.add_constraint>`
depending on scope. Local constraints (on nodes or edges) are checked
when the entity is reached; global constraints are checked throughout
the route.

**Transitions.** Register an update of a variable when the node or edge
is included in a route, via
:meth:`Node.add_transition <grid.Node.add_transition>` or
:meth:`Edge.add_transition <grid.Edge.add_transition>`. The signature is
``add_transition(var, expression)``: when the node or edge is traversed,
``var`` is assigned the value of ``expression``, which may depend on the
current value of ``var`` and any other variables.

Constraints and transitions on nodes apply when the vehicle visits the
node; constraints and transitions on edges apply when the vehicle
traverses the edge.

Custom objectives
-----------------

:meth:`~grid.RoutingModel.set_objective` accepts a ``variables``
parameter in addition to ``metric``. Passing a single :class:`~grid.Var`
or a list of :class:`~grid.Var` instances defines a custom objective:

.. code-block:: python

   model.set_objective(
       variables=[cost_var_on_type_1, cost_var_on_type_2],
       aggregation="max",
   )

When a list of variables is given, each variable must be associated with
a distinct :class:`~grid.VehicleType`, ensuring a one-to-one mapping
between optimisation variables and vehicle types in the fleet. The
aggregation is applied to the final values of the variables at the end
of each route.

Example: ECVRP
--------------

In the Electric Capacitated Vehicle Routing Problem (ECVRP), a fleet of
battery-powered vehicles based at a single depot must serve a set of
customers, each with a positive demand, without exceeding the vehicle
capacity. In addition to customers, the graph contains charging stations:
a vehicle may visit a station to recharge its battery fully, and the same
station may be visited several times. Each vehicle leaves the depot fully
loaded and fully charged. Traversing an edge discharges the battery by an
amount that grows with the distance travelled and with the current load,
through an energy-consumption rate ``r + load / q`` (with ``q`` the
capacity and ``r`` a fixed constant). The battery must never become
negative along any edge. All routes start and end at the depot, and the
objective is to minimise the total travel distance.

This problem cannot be expressed with native features alone, because the
battery discharge along an edge depends on the current value of the load
variable, a coupling that native features do not provide. It is modelled
with three user-defined variables and the expressions that update and
constrain them:

* ``load``: an integer variable tracking the remaining vehicle load,
  initialised to the capacity ``q`` and decreased at each customer.
* ``battery``: a float variable tracking the remaining charge,
  initialised to the maximum level ``b``, decreased along each edge and
  reset to ``b`` at each charging station.
* ``unv_stations``: a set variable holding the stations not yet visited
  since the last customer, used to forbid cycles that consist only of
  charging stations.

.. code-block:: python

   import grid

   # Inputs (provided externally):
   # m: number of vehicles
   # q: vehicle capacity
   # b: maximum and initial battery level
   # customers, stations: sets of customer and station node ids
   # mu[i]: demand of customer i
   # edges: set of edges (i, j) with distance d[i][j]
   # r: fixed battery consumption rate
   # min_from[i]: minimum distance from node i to any next node

   model = grid.RoutingModel()

   v = model.add_vehicle_type(id=0, count=m)
   load = v.add_integer_var(initial_value=q)
   battery = v.add_float_var(initial_value=b, preference="high")

   depot = model.add_node(id=0, depot=True)
   depot.add_constraint(load < q)

   for i in customers:
       customer = model.add_node(id=i)
       customer.add_constraint(load - mu[i] >= 0)
       customer.add_transition(var=load, expression=load - mu[i])

   for s in stations:
       station = model.add_node(id=s, optional=True, max_visits=None)
       station.add_transition(var=battery, expression=b)

   for (i, j) in edges:
       edge = model.add_edge(
           node_from=model.get_node(i),
           node_to=model.get_node(j),
           distance=d[i][j],
       )
       next_battery = battery - d[i][j] * (r + load / q)
       if j not in customers:
           edge.add_constraint(next_battery >= 0)
       else:
           edge.add_transition(var=battery, expression=next_battery)
           edge.add_constraint(
               next_battery >= min_from[j] * (r + (load - mu[j]) / q)
           )

   model.set_objective(metric="distance")

   # Avoid station-only cycles: track unvisited stations along the route
   unv_stations = v.add_nodes_set_var(initial_value=stations)
   for i in customers:
       customer = model.get_node(i)
       customer.add_transition(var=unv_stations, expression=stations)
   for s in stations:
       station = model.get_node(s)
       station.add_constraint(unv_stations.contains(s))
       station.add_transition(
           var=unv_stations, expression=unv_stations.remove(s)
       )

   result = model.solve(solver="LNBS", time_limit=300)

Walkthrough:

* The vehicle type ``v`` carries the two evolving quantities ``load`` and
  ``battery``. ``load`` starts at the capacity ``q``; ``battery`` starts
  at the maximum level ``b`` and is declared with ``preference="high"``,
  since a route reaching a node with more charge is never worse than one
  reaching it with less.
* The depot enforces ``load < q`` as a constraint, requiring that any
  vehicle returning to the depot has served at least one customer.
  Vehicles that never leave the depot remain feasible.
* Customer nodes update ``load`` by subtracting the customer's demand and
  constrain it to remain non-negative.
* Station nodes are optional and may be visited any number of times
  (``max_visits=None``). Visiting a station resets ``battery`` to the
  full level ``b`` without affecting the load.
* Edge behaviour depends on the destination. The discharge along edge
  ``(i, j)`` is ``d[i][j] * (r + load / q)``, which grows with both
  distance and current load. Edges leading to a station or the depot only
  require the residual battery to stay non-negative; edges leading to a
  customer additionally update ``battery`` and require enough residual
  charge to reach at least one further node, accounting for the lower
  load after the customer is served.
* The objective minimises the total travel distance via the
  ``"distance"`` native metric.
* The final block adds the set variable ``unv_stations`` to forbid
  station-only cycles. It is reset to the full set of stations whenever a
  customer is visited; a station may be visited only if it is currently
  in the set, and is removed from the set upon visit.

The same modelling style (declare evolving quantities on the vehicle
type, attach updates and preconditions to nodes and edges, and optionally
register a custom objective) applies to other VRP variants beyond the
scope of native features. For the technical reference of every class and
function used above, see the :doc:`api-reference`.