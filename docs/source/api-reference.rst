API Reference
=============

Technical reference for every public class and function in grid. For a
guided introduction to the modelling style, see the :doc:`quickstart`
and the User Guide.

.. currentmodule:: grid

Modelling Elements
------------------

The four core entities used to describe a problem instance on the
routing graph. Native features are configured via their constructor
parameters and attributes (e.g. node demands, vehicle capacities, time
windows); see each class for the full list, and :doc:`native-features`
for a guided overview.

.. autosummary::
   :toctree: _autosummary
   :recursive:

   RoutingModel
   Node
   Edge
   VehicleType

Variables
---------

User-defined variables declared on a :class:`VehicleType` (via
:meth:`VehicleType.add_integer_var`, :meth:`VehicleType.add_float_var`,
:meth:`VehicleType.add_nodes_set_var`) or globally on a
:class:`RoutingModel`. Combined with Python operators and the functions
below, they enable the custom features described in
:doc:`custom-features`.

.. autosummary::
   :toctree: _autosummary
   :recursive:

   Var
   SetVar

Functions
---------

Free functions used to build expressions in cases where Python operators
do not suffice: element-wise maximum and minimum over a list, square
root, logarithm, and indexing into an array constant.

.. autosummary::
   :toctree: _autosummary

   max
   min
   sqrt
   log
   select