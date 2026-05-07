from __future__ import annotations
from typing import Literal
import numpy as np

class Expr:

    def __init__(self,
                 op:str,
                 type: str,
                 left: Expr=None,
                 right: Expr=None):
        self.op = op
        self.type = type
        self.left=left
        self.right=right

    @staticmethod
    def infer_numeric_type(a, b):
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
        return Expr("+", Expr.infer_numeric_type(self, other), self, other)

    def __radd__(self, other):
        other = Expr._to_expr(other)
        return Expr("+", Expr.infer_numeric_type(self, other), other, self)
    
    def __sub__(self, other):
        other = Expr._to_expr(other)
        return Expr("-", Expr.infer_numeric_type(self, other), self, other)

    def __rsub__(self, other):
        other = Expr._to_expr(other)
        return Expr("-", Expr.infer_numeric_type(self, other), other, self)

    def __mul__(self, other):
        other = Expr._to_expr(other)
        return Expr("*", Expr.infer_numeric_type(self, other), self, other)

    def __rmul__(self, other):
        other = Expr._to_expr(other)
        return Expr("*", Expr.infer_numeric_type(self, other), other, self)

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
            if all(isinstance(elem, (int, np.integer)) for elem in x) and not any(isinstance(elem, bool) for elem in x):
                return ArrayConst("integer_array", x)
            if all(isinstance(elem, (float, np.float64)) for elem in x) and not any(isinstance(elem, bool) for elem in x):
                return ArrayConst("float_array", x)
        raise ValueError(f"Cannot convert object of type {type(x).__name__} to an expression")
        
    @staticmethod
    def max(array: list):
        exprs = [Expr._to_expr(x) for x in array]
        res = exprs[0]
        for e in exprs[1:]:
            res = Expr("max", Expr.infer_numeric_type(res,e), res, e)
        return res
    
    @staticmethod
    def min(array:list):
        exprs = [Expr._to_expr(x) for x in array]
        res = exprs[0]
        for e in exprs[1:]:
            res = Expr("min", Expr.infer_numeric_type(res,e), res, e)
        return res
    
    @staticmethod
    def sqrt(x):
        x = Expr._to_expr(x)
        return Expr("sqrt", "float", x)
    
    @staticmethod
    def log(x, y):
        x = Expr._to_expr(x)
        y = Expr._to_expr(y)
        return Expr("log", "float", x, y)
    
    @staticmethod
    def select(array, key):
        array = Expr._to_expr(array)
        key = Expr._to_expr(key)
        if array.type == "integer_array":
            type = "integer"
        elif array.type == "float_array":
            type = "float"
        else:
            type = "boolean"
        return Expr("select", type, array, key)
        
    def __repr__(self):
        if self.left is None and self.right is None:
            return f"Expr({self.op})"
        return f"Expr({self.op}, {self.left}, {self.right}, {self.type})"


class Var(Expr):

    def __init__(self,
                 id:int,
                 var_type: Literal["integer", "float", "boolean"],
                 initial_value,
                 preference: Literal["low", "high", None]=None):
        self.id = id
        self.type = var_type
        self.initial_value = initial_value
        self.preference = preference

    def __repr__(self):
        return f"Var_{self.id}"
    
    def same(self, other):
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)


class Const(Expr):

    def __init__(self,
                const_type: Literal["integer", "float", "boolean"],
                value):
        self.value=value
        self.type = const_type

    def same(self, other):
        return self.value == other.value

    def __repr__(self):
        return f"Const_{self.value}"
        
    
class ArrayConst(Expr):

    def __init__(self,
                 array_type: Literal["integer_array", "float_array", "boolean_array"],
                 values: list[int]|list[bool]):
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

    def __init__(self,
                 id:int,
                 initial_value):
        self.id = id
        self.type = "setvar"
        self.initial_value = initial_value
        self.preference = None

    def __repr__(self):
        return f"SetVar_{self.id}"
    
    def same(self, other):
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)
    
    def add(self, element):
        return Expr("add", "set", self, SetElem(element))
    
    def contains(self, element):
        return Expr("contains", "boolean", self, SetElem(element))
    
    def is_empty(self):
        return Expr("empty", "boolean", self)
    
    def len(self):
        return Expr("add", "integer", self)
    
    def remove(self, element):
        return Expr("remove", "set", self, SetElem(element))
    
    
class SetConst(Expr):
    def __init__(self,
                 initial_value):
        self.type = "set"
        self.initial_value = initial_value

    def __repr__(self):
        return f"SetConst_{self.initial_value}"
    
    def same(self, other):
        return self.initial_value == other.initial_value
    
    def __hash__(self):
        return hash(self.initial_value)
    
    def contains(self, element):
        return Expr("contains", "boolean", self, Expr._to_expr(element))
    
    def is_empty(self):
        return Expr("empty", "boolean", self)
    
    def len(self):
        return Expr("add", "integer", self)
    
class SetElem(Expr):

    def __init__(self,
                value):
        self.value=value
        
    def same(self, other):
        return self.value == other.value

    def __repr__(self):
        return f"SetElem_{self.value}"
