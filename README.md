# GRID

**GRID** (Graph-based modelling Interface for Domain-Independent Dynamic
Programming) is a Python interface for high-level, declarative modelling of
Vehicle Routing Problems on top of
[Domain-Independent Dynamic Programming](https://didp.ai) (DIDP).

A routing problem is described as a directed graph of nodes, edges, and
vehicle types. Routing requirements are configured either through native
features (predefined attributes with built-in semantics covering common VRP
variants such as CVRP, VRPTW, and PDPTW) or through custom features
(user-defined variables and expressions for variants beyond the native
catalogue, such as the Electric CVRP). GRID compiles the resulting model to
a DyPDL model and solves it with a DIDP solver.

GRID was introduced at CP 2026; see [Citation](#citation) for details.

## Installation

GRID requires Python >= 3.10 and is available on PyPI:

```bash
pip install pygridopt
```

The dependencies ([DIDPPy](https://didppy.readthedocs.io/),
[NetworkX](https://networkx.org/), and [NumPy](https://numpy.org/)) are
installed automatically.

## Example

A minimal Capacitated VRP with three customers, two vehicles of capacity 10,
and a fully connected symmetric graph:

```python
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
```

## Documentation

The documentation is available at
[pygridopt.readthedocs.io](https://pygridopt.readthedocs.io). It includes a
quickstart, a guide to native and custom features with worked PDPTW and
ECVRP examples, and an API reference.

## Citation

If you use GRID in your research, please cite:

```bibtex
@InProceedings{giordana_et_al:LIPIcs.CP.2026.26,
  author =	{Giordana, Fabio and Kiziltan, Zeynep and Kuroiwa, Ryo},
  title =	{{GRID: Graph-Based Modelling Interface for Domain-Independent Dynamic Programming}},
  booktitle =	{32nd International Conference on Principles and Practice of Constraint Programming (CP 2026)},
  pages =	{26:1--26:23},
  series =	{Leibniz International Proceedings in Informatics (LIPIcs)},
  ISBN =	{978-3-95977-432-1},
  ISSN =	{1868-8969},
  year =	{2026},
  volume =	{379},
  editor =	{Beldiceanu, Nicolas},
  publisher =	{Schloss Dagstuhl -- Leibniz-Zentrum f{\"u}r Informatik},
  address =	{Dagstuhl, Germany},
  URL =		{https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2026.26},
  URN =		{urn:nbn:de:0030-drops-266584},
  doi =		{10.4230/LIPIcs.CP.2026.26},
  annote =	{Keywords: Modelling \& Modelling Languages, Dynamic Programming}
}
```

## License

GRID is distributed under the [Apache License 2.0](LICENSE).
