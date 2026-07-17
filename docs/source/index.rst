GRID
====

**GRID** (Graph-based modelling Interface for Domain-Independent Dynamic
Programming) is a high-level Python interface for modelling Vehicle Routing
Problem variants. Routing instances are described as directed graphs of
nodes, edges, and vehicle types, with routing requirements expressed either
through native features (predefined attributes with built-in semantics) or
through custom features (user-defined variables and expressions). GRID
compiles the resulting model to a DyPDL model and solves it with a
Domain-Independent Dynamic Programming solver.

The :doc:`quickstart` provides a minimal end-to-end example. The User
Guide introduces the modelling primitives in order, and the
:doc:`api-reference` documents every class and function.

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   quickstart
   modelling-elements
   native-features
   custom-features

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api-reference