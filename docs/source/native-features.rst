Native Features
===============

Native features are the predefined modelling constructs of GRID whose
semantics are built into the interface. They are set as constructor
arguments of :class:`~grid.Node`, :class:`~grid.Edge`, and
:class:`~grid.VehicleType` (typically through the ``add_*`` methods of
:class:`~grid.RoutingModel`), or selected as parameters of
:meth:`~grid.RoutingModel.set_objective`. Together they let you model many
standard VRP variants without manually encoding state variables,
transitions, or dominance relations.

This page lists the native features grouped by the entity they belong to,
summarises their semantics, and ends with a complete example for the
Pickup and Delivery Problem with Time Windows (PDPTW) that uses only
native features.

Node attributes
---------------

Set when calling
:meth:`RoutingModel.add_node <grid.RoutingModel.add_node>` or the
:class:`~grid.Node` constructor.

``depot`` (bool, default ``False``)
   Whether the node acts as a depot. A model may contain one or more
   depots, and every vehicle starts and ends its route at a depot. When
   several depots exist, a :class:`~grid.VehicleType` can restrict which
   of them its vehicles are allowed to use through ``start_node`` and
   ``end_node``.

``demand`` (number or dict of str to float)
   Demand consumed when the node is visited. A scalar value represents
   single-commodity demand; a dict maps commodity names to per-commodity
   demand for multi-commodity problems. Interacts with the ``capacity``
   attribute of :class:`~grid.VehicleType`.

``tw_start``, ``tw_end`` (float)
   Time window during which service may begin at the node. Service cannot
   start later than ``tw_end``; if the vehicle arrives before
   ``tw_start``, it waits at the node until ``tw_start``.

``service_t`` (float)
   Service time required at the node (time spent before the vehicle can
   leave).

``waiting_t`` (float)
   Maximum waiting time allowed at the node before its time window opens.
   Caps how long a vehicle may wait when it arrives before ``tw_start``.

``pickup``, ``delivery`` (dict of str to float)
   Pickup and delivery quantities per commodity at the node, for
   pickup-and-delivery variants. A delivery of commodity ``"t"`` can only
   be visited if the same vehicle has already visited every pickup of
   ``"t"``. Multi-task pickup/delivery is supported, as well as nodes that
   act as both pickup for one task and delivery for another.

``optional`` (bool, default ``False``)
   Whether the node may be skipped. A non-optional node is mandatory and
   must be visited by exactly one vehicle.

``max_visits`` (int, default ``1``)
   Maximum number of times the node may be visited. ``None`` allows
   unlimited visits (useful for charging stations, refuelling points, etc.).

Edge attributes
---------------

Set when calling
:meth:`RoutingModel.add_edge <grid.RoutingModel.add_edge>` or the
:class:`~grid.Edge` constructor.

``distance`` (float)
   Travel distance along the edge. Used by the ``"distance"`` objective
   metric and as input to dual-bound computations.

``travel_time`` (float)
   Travel time along the edge. Used by time-window enforcement, the
   ``"time"`` objective metric, and related dual bounds.

VehicleType attributes
----------------------

Set when calling
:meth:`RoutingModel.add_vehicle_type <grid.RoutingModel.add_vehicle_type>`
or the :class:`~grid.VehicleType` constructor.

``count`` (int, default ``1``)
   Number of vehicles of this type available.

``capacity`` (number or dict of str to float)
   Vehicle capacity. Scalar for single-commodity, dict mapping commodity
   names to per-commodity capacity for multi-commodity problems.

``start_node``, ``end_node`` (int)
   Depot at which vehicles of this type start and end. Every route begins
   and ends at a depot; these attributes select which depot is used by
   this vehicle type when the model contains more than one. With a single
   depot they can be omitted.

Model-level options
-------------------

``triangular_inequality`` (bool, default ``True``)
   Constructor argument of :class:`~grid.RoutingModel`. States whether
   the distance and time data satisfy the triangular inequality. Set to
   ``False`` only when modelling instances with explicit violations of
   this property.

Built-in objectives
-------------------

A built-in objective is selected through
:meth:`~grid.RoutingModel.set_objective` with the following parameters:

* ``metric`` selects a built-in metric: ``"distance"``, ``"time"``, or
  ``"num_vehicles"``.
* ``aggregation`` combines per-route contributions: ``"sum"`` (default)
  or ``"max"``.
* ``maximize`` toggles between minimisation (default) and maximisation.

Example: PDPTW
--------------

In the Pickup and Delivery Problem with Time Windows (PDPTW), a fleet of
identical vehicles based at a single depot must serve a set of transport
tasks. Each task couples a pickup location with a delivery location: the
goods picked up at the former must be dropped off at the latter by the
same vehicle, and the pickup must precede the delivery along the route.
Every location has a demand, a service time, and a time window; a vehicle
arriving before the window opens waits until it does, and service cannot
begin after the window closes. Vehicle capacity must be respected at all
times, since load accumulates between a pickup and its delivery. All
routes start and end at the depot, and the objective is to minimise the
total travel distance.

The model below is a complete formulation of the PDPTW using only native
features.

.. code-block:: python

   import grid

   # Inputs (provided externally):
   # m: number of vehicles
   # q: vehicle capacity
   # tasks: list of pickup-and-delivery tasks
   # p[t], d[t]: pickup and delivery node ids for task t
   # a[i], b[i], s[i]: time window and service time of node i
   # mu[i]: demand of node i
   # edges: set of edges (i, j) with travel time c[i][j]

   model = grid.RoutingModel()

   model.add_vehicle_type(id=0, count=m, capacity=q)

   model.add_node(id=0, tw_start=a[0], tw_end=b[0], depot=True)

   for t in tasks:
       model.add_node(
           id=p[t],
           pickup={f"{t}": mu[p[t]]},
           tw_start=a[p[t]], tw_end=b[p[t]], service_t=s[p[t]],
       )
       model.add_node(
           id=d[t],
           delivery={f"{t}": mu[d[t]]},
           tw_start=a[d[t]], tw_end=b[d[t]], service_t=s[d[t]],
       )

   for (i, j) in edges:
       model.add_edge(
           node_from=model.get_node(i),
           node_to=model.get_node(j),
           distance=c[i][j],
       )

   model.set_objective(metric="distance")

   result = model.solve(solver="LNBS", time_limit=300)

Walkthrough:

* A single :class:`~grid.VehicleType` defines a homogeneous fleet of ``m``
  vehicles with capacity ``q``.
* The depot node is created with its time window and the ``depot`` flag.
* For each pickup-and-delivery task, two nodes are added: one with a
  ``pickup`` attribute that links it to the task identifier and pickup
  quantity, the other with a ``delivery`` attribute for the corresponding
  delivery. GRID's native semantics ensure that, for every task, the
  delivery node can be served only after the corresponding pickup has been
  served by the same vehicle, that vehicle capacity is respected, and that
  time windows are honoured.
* Edges are added with their travel time (equivalent to travel distance in
  this problem).
* The objective metric ``"distance"`` aggregates edge distances along all
  routes by sum and minimises the total. Other built-in metrics include
  ``"time"`` and ``"num_vehicles"``; aggregation can be switched to
  ``"max"`` and direction reversed with ``maximize=True``.

When the requirements of a problem cannot be captured by these native
features alone (for example, a resource whose update along an edge
depends on the current value of another variable, as in the
electric-vehicle battery model of the next page), see
:doc:`custom-features`.