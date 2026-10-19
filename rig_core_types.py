"""user.rig_core_types(): the named sets of values rigs take, each
value described. A param that takes one says so in its docstring:
`Type: rig_core.easing`.

Read from the tables the code runs on, so there is no list to keep in
step.
"""

from talon import Module

from .src.easing import EASINGS
from .src.contracts import MODES, INTERPOLATIONS, BEHAVIORS

mod = Module()


def _values(table: dict) -> list:
    return [{"id": name, "desc": v[1] if isinstance(v, tuple) else v}
            for name, v in table.items()]


def types() -> dict:
    return {
        "easing": {"desc": "How a change paces itself over its time.",
                   "values": _values(EASINGS)},
        "interpolation": {"desc": "How a direction or vector gets from one value to the other.",
                          "values": _values(INTERPOLATIONS)},
        "mode": {"desc": "What a layer does to the value coming into it.",
                 "values": _values(MODES)},
        "behavior": {"desc": "What happens when a change fires again while the last one "
                             "is still running. 'to' replaces by default; the rest stack.",
                     "values": _values(BEHAVIORS)},
    }


@mod.action_class
class Actions:
    def rig_core_types() -> dict:
        """Named sets of values rigs take, each value described:
        {name: {"desc": str, "values": [{"id": str, "desc": str}]}}"""
        return types()
