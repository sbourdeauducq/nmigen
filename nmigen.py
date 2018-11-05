import tracer


class Context:
    def __init__(self):
        self.modules = []
        self.stack = []
        self.last_if = None

    def get(self, ty):
        for entry in reversed(self.stack):
            if isinstance(entry, ty):
                return entry
        raise ValueError

global_context = Context()


class Stackable:
    def __init__(self):
        self.pending_statements = []

    def __enter__(self):
        global_context.stack.append(self)

    def __exit__(self, ty, value, traceback):
        when = global_context.get((Module, Comb, Sync))
        if isinstance(when, (Module, Comb)):
            when = None
        else:
            when = when.clock_domain
        
        statements = []
        for statement in self.pending_statements:
            if isinstance(statement, _Operator):
                assert statement.op == "<="
                statements.append(_Assign(when, *statement.operands))
            else:
                statements.append(statement)
        self.collect_statements(statements)
        self.pending_statements = []
        element = global_context.stack.pop()
        assert element == self

    def collect_statements(self, statements):
        raise NotImplementedError


class StatementCollector:
    pass


class Module(Stackable, StatementCollector):
    def __init__(self, name):
        Stackable.__init__(self)
        self.name = name
        self.statements = []
        global_context.modules.append(self)

    def collect_statements(self, statements):
        self.statements += statements


class Comb(Stackable):
    def collect_statements(self, statements):
        global_context.get(StatementCollector).pending_statements += statements


class Sync(Stackable):
    def __init__(self, clock_domain="sys"):
        Stackable.__init__(self)
        self.clock_domain = clock_domain

    def collect_statements(self, statements):
        global_context.get(StatementCollector).pending_statements += statements


class _Value:
    def __bool__(self):
        # Special case: Constants and Signals are part of a set or used as
        # dictionary keys, and Python needs to check for equality.
        if isinstance(self, _Operator) and self.op == "==":
            a, b = self.operands
            if isinstance(a, Constant) and isinstance(b, Constant):
                return a.value == b.value
            if isinstance(a, Signal) and isinstance(b, Signal):
                return a is b
            if (isinstance(a, Constant) and isinstance(b, Signal)
                    or isinstance(a, Signal) and isinstance(b, Constant)):
                return False
        raise TypeError("Attempted to convert Migen value to boolean")

    def __invert__(self):
        return _Operator("~", [self])
    def __neg__(self):
        return _Operator("-", [self])

    def __add__(self, other):
        return _Operator("+", [self, other])
    def __radd__(self, other):
        return _Operator("+", [other, self])
    def __sub__(self, other):
        return _Operator("-", [self, other])
    def __rsub__(self, other):
        return _Operator("-", [other, self])
    def __mul__(self, other):
        return _Operator("*", [self, other])
    def __rmul__(self, other):
        return _Operator("*", [other, self])
    def __lshift__(self, other):
        return _Operator("<<<", [self, other])
    def __rlshift__(self, other):
        return _Operator("<<<", [other, self])
    def __rshift__(self, other):
        return _Operator(">>>", [self, other])
    def __rrshift__(self, other):
        return _Operator(">>>", [other, self])
    def __and__(self, other):
        return _Operator("&", [self, other])
    def __rand__(self, other):
        return _Operator("&", [other, self])
    def __xor__(self, other):
        return _Operator("^", [self, other])
    def __rxor__(self, other):
        return _Operator("^", [other, self])
    def __or__(self, other):
        return _Operator("|", [self, other])
    def __ror__(self, other):
        return _Operator("|", [other, self])

    def __lt__(self, other):
        return _Operator("<", [self, other])

    def __le__(self, other):
        if isinstance(other, _Operator) and other.op == "<=":
            global_context.pending_statements.remove(other)
        operation = _Operator("<=", [self, other])
        global_context.get(Stackable).pending_statements.append(operation)
        return operation

    def __eq__(self, other):
        return _Operator("==", [self, other])
    def __ne__(self, other):
        return _Operator("!=", [self, other])
    def __gt__(self, other):
        return _Operator(">", [self, other])
    def __ge__(self, other):
        return _Operator(">=", [self, other])
    def __hash__(self):
        raise TypeError("unhashable type: '{}'".format(type(self).__name__))


class Signal(_Value):
    def __init__(self, nbits=1, name=None):
        if name is None:
            name = tracer.get_var_name()
        self.name = name
        self.nbits = nbits

    def __repr__(self):
        return "({})".format(self.name)


class Constant(_Value):
    """A constant, HDL-literal integer `_Value`

    Parameters
    ----------
    value : int
    bits_sign : int or tuple or None
        Either an integer `bits` or a tuple `(bits, signed)`
        specifying the number of bits in this `Constant` and whether it is
        signed (can represent negative values). `bits_sign` defaults
        to the minimum width and signedness of `value`.
    """
    def __init__(self, value, bits_sign=None):
        self.value = int(value)
        if bits_sign is None:
            bits_sign = self.value.bit_length(), self.value < 0
        elif isinstance(bits_sign, int):
            bits_sign = bits_sign, self.value < 0
        self.nbits, self.signed = bits_sign
        if not isinstance(self.nbits, int) or self.nbits < 0:
            raise TypeError("Width must be a positive integer")

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return "({}'{}d{})".format(self.nbits, "s" if self.signed else "", self.value)


C = Constant  # shorthand


def wrap(value):
    """Ensures that the passed object is a Migen value. Booleans and integers
    are automatically wrapped into ``Constant``."""
    if isinstance(value, (bool, int)):
        value = Constant(value)
    if not isinstance(value, _Value):
        raise TypeError("Object '{}' of type {} is not a Migen value"
                        .format(value, type(value)))
    return value


class _Operator(_Value):
    def __init__(self, op, operands):
        _Value.__init__(self)
        self.op = op
        self.operands = [wrap(o) for o in operands]

    def __repr__(self):
        if len(self.operands) == 1:
            return "({} {})".format(self.op, self.operands[0])
        elif len(self.operands) == 2:
            return "({} {} {})".format(self.operands[0], self.op, self.operands[1])


class _Assign:
    def __init__(self, when, l, r):
        self.when = when
        self.l = wrap(l)
        self.r = wrap(r)

    def __repr__(self):
        return "{}: {} = {}".format(self.when, self.l, self.r)


class If(Stackable, StatementCollector):
    def __init__(self, condition):
        Stackable.__init__(self)
        self.condition = condition
        self.then_statements = []
        self.else_statement = None
        global_context.get(Stackable).pending_statements.append(self)

    def __exit__(self, ty, value, traceback):
        Stackable.__exit__(self, ty, value, traceback)
        global_context.last_if = self

    def collect_statements(self, statements):
        self.then_statements += statements

    def __repr__(self):
        return "if {} then {} else {}".format(self.condition, self.then_statements,
            [] if self.else_statement is None else self.else_statement.statements)


class Else(Stackable, StatementCollector):
    def __init__(self):
        Stackable.__init__(self)
        self.statements = []

    def __enter__(self):
        Stackable.__enter__(self)
        assert global_context is not None
        global_context.last_if.else_statement = self

    def __exit__(self, ty, value, traceback):
        Stackable.__exit__(self, ty, value, traceback)
        global_context.last_if = None

    def collect_statements(self, statements):
        self.statements += statements
