from nmigen import *
from fsm import *

with Module("top"):
    a = Signal()
    b = Signal()
    c = Signal()

    x = Signal()
    b <= 2
    with If(x):
        b <= c
        with Sync("foo"):
            a <= a + 1

    y = Signal()
    with Sync():
        with If(y):
            with Comb():
                a <= 3
        with Else():
            c <= 1

    start = Signal()
    running = Signal(1)
    count = Signal(3)
    fsm = FSM()

    with fsm.act("IDLE"):
        with Sync():
            count <= 0
        with If(start):
            next_state("RUNNING")

    with fsm.act("RUNNING"):
        running <= 1
        with Sync():
            count <= count + 1
        with If(count == 4):
            next_state("IDLE")

    fsm.finalize()


print(global_context.modules[0].statements)
