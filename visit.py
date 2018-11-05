from nmigen import *
from nmigen import _Operator, _Assign


class NodeTransformer:
    def visit(self, node):
        if isinstance(node, Constant):
            return self.visit_Constant(node)
        elif isinstance(node, Signal):
            return self.visit_Signal(node)
        elif isinstance(node, _Operator):
            return self.visit_Operator(node)
        elif isinstance(node, _Assign):
            return self.visit_Assign(node)
        elif isinstance(node, If):
            return self.visit_If(node)
        elif isinstance(node, (list, tuple)):
            return self.visit_statements(node)
        else:
            return self.visit_unknown(node)

    # values
    def visit_Constant(self, node):
        return node

    def visit_Signal(self, node):
        return node

    def visit_Operator(self, node):
        return _Operator(node.op, [self.visit(o) for o in node.operands])

    # statements
    def visit_Assign(self, node):
        if node.when is None:
            with Comb():
                self.visit(node.l) <= self.visit(node.r)
        else:
            with Sync(node.when):
                self.visit(node.l) <= self.visit(node.r)

    def visit_If(self, node):
        with If(self.visit(node.condition)):
            self.visit(node.then_statements)
        if node.else_statement is not None:
            with Else():
                self.visit(node.else_statement.statements)

    def visit_statements(self, node):
        for statement in node:
            self.visit(statement)

    def visit_unknown(self, node):
        return node
