import warnings
from collections import OrderedDict

from nmigen import *
import tracer
import visit


class NextState:
    def __init__(self, state_id):
        self.state_id = state_id


def next_state(state_id):
    global_context.get(StatementCollector).collect_statements([NextState(state_id)])


class LowerNextState(visit.NodeTransformer):
    def __init__(self, fsm):
        self.fsm = fsm

    def visit_unknown(self, node):
        if isinstance(node, NextState):
            encoding = list(self.fsm.actions.keys()).index(node.state_id)
            self.fsm.next_state <= encoding
        else:
            return node


class FSMAction(Stackable, StatementCollector):
    def __init__(self, fsm):
        Stackable.__init__(self)
        self.fsm = fsm
        self.statements = []

    def collect_statements(self, statements):
        self.statements += statements


class FSM:
    def __init__(self, name=None):
        if name is None:
            name = tracer.get_var_name()
        self.name = name
        self.module = global_context.get(Module)
        self.actions = OrderedDict()
        self.finalized = False

    def act(self, state_id):
        assert not self.finalized
        try:
            action = self.actions[state_id]
        except KeyError:
            action = FSMAction(self)
            self.actions[state_id] = action
        return action

    def finalize(self):
        assert not self.finalized
        self.finalized = True

        nbits = len(self.actions).bit_length()
        self.state = Signal(nbits, name=self.name + "_state")
        self.next_state = Signal(nbits, name=self.name + "_next_state")

        with self.module:
            self.next_state <= self.state

            lns = LowerNextState(self)
            # TODO: use Case (unless synthesizers are OK with If?)
            for state, fsm_action in enumerate(self.actions.values()):
                with If(self.state == state):
                    lns.visit(fsm_action.statements)

    def __del__(self):
        if not self.finalized:
            warnings.warn("FSM \"{}\" in module \"{}\" was not finalized".format(self.name, self.module.name))
