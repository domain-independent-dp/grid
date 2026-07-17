"""Expression hierarchy for building constraints and objectives in GRID.

Defines :class:`Expr` (the base node of the expression tree) and its concrete
subclasses :class:`Var`, :class:`Const`, :class:`ArrayConst`, :class:`SetVar`,
:class:`SetConst`, and :class:`SetElem`. Python arithmetic, comparison, and
logical operators are overloaded on :class:`Expr` to allow building
expressions with natural Python syntax.
"""

from __future__ import annotations

from typing import Literal

import numpy as np


class Expr:
    """Base class of the GRID expression tree.

    An :class:`Expr` is a node in an algebraic expression tree built from
    operands and operators. Python's arithmetic (``+``, ``-``, ``*``, ``/``,
    ``//``, ``%``), comparison (``<``, ``<=``, ``==``, ``!=``, ``>=``, ``>``),
    and logical (``&``, ``|``, ``~``) operators are overloaded so that
    combining :class:`Var`, :class:`Const`, and other :class:`Expr` instances
    with these operators automatically builds a new :class:`Expr`.

    Concrete subclasses (:class:`Var`, :class:`Const`, :class:`ArrayConst`,
    :class:`SetVar`, :class:`SetConst`, :class:`SetElem`) represent the leaves
    of the tree; interior nodes are created by operator overloads and by the
    static factory methods :meth:`max`, :meth:`min`, :meth:`sqrt`, :meth:`log`,
    :meth:`select`.

    Users typically do not construct :class:`Expr` directly. Expression trees are
    built via operator overloading on :class:`Var` and :class:`SetVar`, and through
    :func:`max`, :func:`min`, :func:`sqrt`, :func:`log`, and :func:`select`.
    :class:`Expr` is not part of the top-level public API.

    Parameters
    ----------
    op : str
        Symbol identifying the operator at this node (e.g. ``"+"``, ``"max"``,
        ``"select"``).
    type : str
        Numeric or logical type of the expression's value, one of
        ``"integer"``, ``"float"``, ``"boolean"``, ``"integer_array"``,
        ``"float_array"``, ``"boolean_array"``, ``"set"``, or ``"setvar"``.
    left : Expr, optional
        Left operand.
    right : Expr, optional
        Right operand. ``None`` for unary operators.

    Attributes
    ----------
    op : str
        Operator symbol.
    type : str
        Expression type.
    left : Expr or None
        Left operand.
    right : Expr or None
        Right operand.
    """

    def __init__(self, op: str, type: str, left: Expr = None, right: Expr = None):
        self.op = op
        self.type = type
        self.left = left
        self.right = right

    @staticmethod
    def _infer_numeric_type(a, b):
        """Return the numeric type resulting from combining two expressions.

        Returns ``"integer"`` if both expressions are integer, ``"float"``
        otherwise.

        Parameters
        ----------
        a : Expr
            First operand.
        b : Expr
            Second operand.

        Returns
        -------
        {"integer", "float"}
        """
        if a.type == "integer" and b.type == "integer":
            return "integer"
        return "float"

    def __le__(self, other):
        other = Expr._to_expr(other)
        return Expr("<=", "boolean", self, other)

    def __lt__(self, other):
        other = Expr._to_expr(other)
        return Expr("<", "boolean", self, other)

    def __ge__(self, other):
        other = Expr._to_expr(other)
        return Expr(">=", "boolean", self, other)

    def __gt__(self, other):
        other = Expr._to_expr(other)
        return Expr(">", "boolean", self, other)

    def __eq__(self, other):
        other = Expr._to_expr(other)
        return Expr("==", "boolean", self, other)

    def __ne__(self, other):
        other = Expr._to_expr(other)
        return Expr("!=", "boolean", self, other)

    def __pos__(self):
        return Expr("pos", self.type, self)

    def __neg__(self):
        return Expr("neg", self.type, self)

    def __add__(self, other):
        other = Expr._to_expr(other)
        return Expr("+", Expr._infer_numeric_type(self, other), self, other)

    def __radd__(self, other):
        other = Expr._to_expr(other)
        return Expr("+", Expr._infer_numeric_type(self, other), other, self)

    def __sub__(self, other):
        other = Expr._to_expr(other)
        return Expr("-", Expr._infer_numeric_type(self, other), self, other)

    def __rsub__(self, other):
        other = Expr._to_expr(other)
        return Expr("-", Expr._infer_numeric_type(self, other), other, self)

    def __mul__(self, other):
        other = Expr._to_expr(other)
        return Expr("*", Expr._infer_numeric_type(self, other), self, other)

    def __rmul__(self, other):
        other = Expr._to_expr(other)
        return Expr("*", Expr._infer_numeric_type(self, other), other, self)

    def __truediv__(self, other):
        other = Expr._to_expr(other)
        return Expr("/", "float", self, other)

    def __rtruediv__(self, other):
        other = Expr._to_expr(other)
        return Expr("/", "float", other, self)

    def __floordiv__(self, other):
        other = Expr._to_expr(other)
        return Expr("//", "integer", self, other)

    def __rfloordiv__(self, other):
        other = Expr._to_expr(other)
        return Expr("//", "integer", other, self)

    def __mod__(self, other):
        other = Expr._to_expr(other)
        return Expr("%", "integer", self, other)

    def __rmod__(self, other):
        other = Expr._to_expr(other)
        return Expr("%", "integer", other, self)

    def __and__(self, other):
        other = Expr._to_expr(other)
        return Expr("&", "boolean", self, other)

    def __rand__(self, other):
        other = Expr._to_expr(other)
        return Expr("&", "boolean", other, self)

    def __or__(self, other):
        other = Expr._to_expr(other)
        return Expr("|", "boolean", self, other)

    def __ror__(self, other):
        other = Expr._to_expr(other)
        return Expr("|", "boolean", other, self)

    def __invert__(self):
        Expr._validate_boolean(self)
        return Expr("~", "boolean", self)

    @staticmethod
    def _to_expr(x):
        if isinstance(x, Expr):
            return x
        if isinstance(x, set):
            return SetConst(x)
        if isinstance(x, bool):
            return Const("boolean", x)
        if isinstance(x, (int, np.integer)):
            return Const("integer", x)
        if isinstance(x, (float, np.float64)):
            return Const("float", x)
        if isinstance(x, list):
            if all(isinstance(elem, bool) for elem in x):
                return ArrayConst("boolean_array", x)
            if all(isinstance(elem, (int, np.integer)) for elem in x) and not any(
                isinstance(elem, bool) for elem in x
            ):
                return ArrayConst("integer_array", x)
            if all(isinstance(elem, (float, np.float64)) for elem in x) and not any(
                isinstance(elem, bool) for elem in x
            ):
                return ArrayConst("float_array", x)
        raise ValueError(f"Cannot convert object of type {type(x).__name__} to an expression")

    def __repr__(self):
        if self.left is None and self.right is None:
            return f"Expr({self.op})"
        return f"Expr({self.op}, {self.left}, {self.right}, {self.type})"


def max(array):
    """Return an expression evaluating to the element-wise maximum of inputs.

    Parameters
    ----------
    array : list of Expr, Var, or numeric
        Inputs to compare. Python literals are wrapped automatically.

    Returns
    -------
    Expr
        Expression representing ``max(array)``.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> load = vehicle.add_integer_var(initial_value=10)
    >>> grid.max([load, 0])
    Expr(max, Var_0, Const_0, integer)
    """
    exprs = [Expr._to_expr(x) for x in array]
    res = exprs[0]
    for e in exprs[1:]:
        res = Expr("max", Expr._infer_numeric_type(res, e), res, e)
    return res


def min(array):
    """Return an expression evaluating to the element-wise minimum of inputs.

    Parameters
    ----------
    array : list of Expr, Var, or numeric
        Inputs to compare. Python literals are wrapped automatically.

    Returns
    -------
    Expr
        Expression representing ``min(array)``.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> load = vehicle.add_integer_var(initial_value=10)
    >>> grid.min([load, 5])
    Expr(min, Var_0, Const_5, integer)
    """
    exprs = [Expr._to_expr(x) for x in array]
    res = exprs[0]
    for e in exprs[1:]:
        res = Expr("min", Expr._infer_numeric_type(res, e), res, e)
    return res


def sqrt(x):
    """Return an expression evaluating to the square root of ``x``.

    Parameters
    ----------
    x : Expr, Var, or numeric
        Operand. The result has type ``"float"``.

    Returns
    -------
    Expr

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> load = vehicle.add_integer_var(initial_value=10)
    >>> grid.sqrt(load)
    Expr(sqrt, Var_0, None, float)
    """
    x = Expr._to_expr(x)
    return Expr("sqrt", "float", x)


def log(x, y):
    """Return an expression evaluating to a logarithm.

    Parameters
    ----------
    x : Expr, Var, or numeric
        Argument of the logarithm.
    y : Expr, Var, or numeric
        Base of the logarithm.

    Returns
    -------
    Expr
        Float-typed logarithm expression.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> load = vehicle.add_integer_var(initial_value=10)
    >>> grid.log(load, 2)
    Expr(log, Var_0, Const_2, float)
    """
    x = Expr._to_expr(x)
    y = Expr._to_expr(y)
    return Expr("log", "float", x, y)


def select(array, key):
    """Return an expression indexing an array expression at a key.

    Parameters
    ----------
    array : Expr or list
        Array expression (or Python list wrapped into :class:`ArrayConst`).
    key : Expr or int
        Index expression.

    Returns
    -------
    Expr
        Expression of type ``"integer"``, ``"float"``, or ``"boolean"``
        depending on the array's element type.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> position = vehicle.add_integer_var(initial_value=0)
    >>> grid.select([10, 20, 30], position)
    Expr(select, ArrayConst_[10, 20, 30], Var_0, integer)
    """
    array = Expr._to_expr(array)
    key = Expr._to_expr(key)
    if array.type == "integer_array":
        type = "integer"
    elif array.type == "float_array":
        type = "float"
    else:
        type = "boolean"
    return Expr("select", type, array, key)


class Var(Expr):
    """Decision variable of the model.

    Returned by the variable-creation methods of :class:`RoutingModel` and
    :class:`VehicleType` (``add_integer_var``, ``add_float_var``,
    ``add_nodes_set_var``). Subclass of :class:`Expr` so that variables can be
    combined with other expressions through operator overloading.

    Instances are typically obtained via :meth:`RoutingModel.add_integer_var`,
    :meth:`RoutingModel.add_float_var`, or the equivalent methods on
    :class:`VehicleType`, not constructed directly..

    Parameters
    ----------
    id : int
        Unique identifier of the variable within the model.
    var_type : {"integer", "float", "boolean"}
        Numeric type of the variable's value.
    initial_value : int, float, or bool
        Value of the variable at the start of the route.
    preference : {"low", "high", None}, default: None
        Solver hint indicating preferred direction during search.

    Attributes
    ----------
    id : int
        Variable identifier.
    type : str
        Numeric type (same as ``var_type``).
    initial_value : int, float, or bool
        initial value.
    preference : str or None
        Solver preference hint.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> load = vehicle.add_integer_var(initial_value=10)
    >>> load
    Var_0
    >>> load - 3
    Expr(-, Var_0, Const_3, integer)
    >>> load >= 0
    Expr(>=, Var_0, Const_0, boolean)
    """

    def __init__(
        self,
        id: int,
        var_type: Literal["integer", "float", "boolean"],
        initial_value,
        preference: Literal["low", "high", None] = None,
    ):
        self.id = id
        self.type = var_type
        self.initial_value = initial_value
        self.preference = preference

    def __repr__(self):
        return f"Var_{self.id}"

    def same(self, other):
        """Return whether this variable refers to the same id as ``other``.

        Distinct from ``__eq__``, which is overloaded to build a boolean
        :class:`Expr` for use in constraints.

        Parameters
        ----------
        other : Var

        Returns
        -------
        bool

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> load = vehicle.add_integer_var(initial_value=10)
        >>> battery = vehicle.add_float_var(initial_value=100.0)
        >>> load.same(load)
        True
        >>> load.same(battery)
        False
        """
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


class Const(Expr):
    """Constant scalar value wrapped as an expression.

    Used internally to lift Python literals into the expression tree when they
    are combined with :class:`Expr` operands; users rarely need to construct
    :class:`Const` directly.

    Parameters
    ----------
    const_type : {"integer", "float", "boolean"}
        Type of the constant.
    value : int, float, or bool
        Literal value.

    Attributes
    ----------
    value : int, float, or bool
        Literal value.
    type : str
        Constant type (same as ``const_type``).
    """

    def __init__(self, const_type: Literal["integer", "float", "boolean"], value):
        self.value = value
        self.type = const_type

    def same(self, other):
        """Return whether this constant has the same value as ``other``.

        Parameters
        ----------
        other : Const

        Returns
        -------
        bool
        """
        return self.value == other.value

    def __repr__(self):
        return f"Const_{self.value}"


class ArrayConst(Expr):
    """Constant 1D array wrapped as an expression.

    Supports indexing via ``array[key]`` (where ``key`` may be a Python int or
    an :class:`Expr`), iteration, and ``len()``.

    Parameters
    ----------
    array_type : {"integer_array", "float_array", "boolean_array"}
        Type of the array's elements.
    values : list of int, float, or bool
        Literal values.

    Attributes
    ----------
    values : list
        Literal values.
    type : str
        Array type (same as ``array_type``).
    """

    def __init__(
        self,
        array_type: Literal["integer_array", "float_array", "boolean_array"],
        values: list[int] | list[bool],
    ):
        self.values = values
        self.type = array_type

    def __getitem__(self, key):
        key = Expr._to_expr(key)
        if self.type == "integer_array":
            type = "integer"
        elif self.type == "float_array":
            type = "float"
        else:
            type = "boolean"
        return Expr("select", type, self, key)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return f"ArrayConst_{self.values}"


class SetVar(Expr):
    """Set-valued decision variable, with elements from the node-id universe.

    Returned by :meth:`RoutingModel.add_nodes_set_var` and
    :meth:`VehicleType.add_nodes_set_var`. Provides set-algebra methods
    (:meth:`add`, :meth:`remove`, :meth:`contains`, :meth:`is_empty`,
    :meth:`len`) that build :class:`Expr` instances usable in constraints
    and transitions.

    Instances are typically obtained via
    :meth:`RoutingModel.add_nodes_set_var` and
    :meth:`VehicleType.add_nodes_set_var`, not constructed directly.

    Parameters
    ----------
    id : int
        Unique identifier of the variable.
    initial_value : set or list
        Initial contents of the set.

    Attributes
    ----------
    id : int
        Variable identifier.
    type : str
        Always ``"setvar"``.
    initial_value : set or list
        Initial contents.
    preference : None
        Set variables do not carry a solver preference.

    Examples
    --------
    >>> import grid
    >>> model = grid.RoutingModel()
    >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
    >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
    >>> stations
    SetVar_0
    >>> stations.contains(3)
    Expr(contains, SetVar_0, SetElem_3, boolean)
    >>> stations.remove(3)
    Expr(remove, SetVar_0, SetElem_3, set)
    """

    def __init__(self, id: int, initial_value):
        self.id = id
        self.type = "setvar"
        self.initial_value = initial_value
        self.preference = None

    def __repr__(self):
        return f"SetVar_{self.id}"

    def same(self, other):
        """Return whether this set variable refers to the same id as ``other``.

        Parameters
        ----------
        other : SetVar

        Returns
        -------
        bool

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> s1 = vehicle.add_nodes_set_var(initial_value={1})
        >>> s2 = vehicle.add_nodes_set_var(initial_value={2})
        >>> s1.same(s1)
        True
        >>> s1.same(s2)
        False
        """
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def add(self, element):
        """Return an expression representing the set with ``element`` added.

        Parameters
        ----------
        element : int or Expr
            Element to add.

        Returns
        -------
        Expr
            Expression of type ``"set"``.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
        >>> stations.add(5)
        Expr(add, SetVar_0, SetElem_5, set)
        """
        return Expr("add", "set", self, SetElem(element))

    def contains(self, element):
        """Return a boolean expression testing membership of ``element``.

        Parameters
        ----------
        element : int or Expr
            Element to test.

        Returns
        -------
        Expr
            Boolean expression.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
        >>> stations.contains(3)
        Expr(contains, SetVar_0, SetElem_3, boolean)
        """
        return Expr("contains", "boolean", self, SetElem(element))

    def is_empty(self):
        """Return a boolean expression testing whether the set is empty.

        Returns
        -------
        Expr
            Boolean expression.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
        >>> stations.is_empty()
        Expr(empty, SetVar_0, None, boolean)
        """
        return Expr("empty", "boolean", self)

    def len(self):
        """Return an integer expression giving the cardinality of the set.

        Returns
        -------
        Expr
            Integer expression.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
        >>> stations.len()
        Expr(add, SetVar_0, None, integer)
        """
        return Expr("add", "integer", self)

    def remove(self, element):
        """Return an expression representing the set with ``element`` removed.

        Parameters
        ----------
        element : int or Expr
            Element to remove.

        Returns
        -------
        Expr
            Expression of type ``"set"``.

        Examples
        --------
        >>> import grid
        >>> model = grid.RoutingModel()
        >>> vehicle = model.add_vehicle_type(id=0, count=1, capacity=10)
        >>> stations = vehicle.add_nodes_set_var(initial_value={3, 4})
        >>> stations.remove(4)
        Expr(remove, SetVar_0, SetElem_4, set)
        """
        return Expr("remove", "set", self, SetElem(element))


class SetConst(Expr):
    """Constant set wrapped as an expression.

    Used internally to lift Python ``set`` literals into the expression tree
    when they are combined with :class:`Expr` operands.

    Parameters
    ----------
    initial_value : set
        Set contents.

    Attributes
    ----------
    initial_value : set
        Set contents.
    type : str
        Always ``"set"``.
    """

    def __init__(self, initial_value):
        self.type = "set"
        self.initial_value = initial_value

    def __repr__(self):
        return f"SetConst_{self.initial_value}"

    def same(self, other):
        """Return whether this set constant has the same contents as ``other``.

        Parameters
        ----------
        other : SetConst

        Returns
        -------
        bool
        """
        return self.initial_value == other.initial_value

    def __hash__(self):
        return hash(self.initial_value)

    def contains(self, element):
        """Return a boolean expression testing membership of ``element``.

        Parameters
        ----------
        element : int or Expr

        Returns
        -------
        Expr
        Boolean expression.
        """
        return Expr("contains", "boolean", self, Expr._to_expr(element))

    def is_empty(self):
        """Return a boolean expression testing whether the set is empty.

        Returns
        -------
        Expr
            Boolean expression.
        """
        return Expr("empty", "boolean", self)

    def len(self):
        """Return an integer expression giving the cardinality of the set.

        Returns
        -------
        Expr
            Integer expression.
        """
        return Expr("add", "integer", self)


class SetElem(Expr):
    """Single set element wrapped as an expression.

    Used internally by :meth:`SetVar.add`, :meth:`SetVar.remove`, and
    :meth:`SetVar.contains` to wrap the element being added, removed, or
    tested.

    Parameters
    ----------
    value : int or Expr
        The element.

    Attributes
    ----------
    value : int or Expr
    """

    def __init__(self, value):
        self.value = value

    def same(self, other):
        """Return whether this element has the same value as ``other``.

        Parameters
        ----------
        other : SetElem

        Returns
        -------
        bool
        """
        return self.value == other.value

    def __repr__(self):
        return f"SetElem_{self.value}"
