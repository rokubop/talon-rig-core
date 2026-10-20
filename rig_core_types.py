"""Value sets for user.rig_core_types(), built from the tables the code runs on."""

from talon import Module

from .src.easing import EASINGS
from .src.contracts import MODES, INTERPOLATIONS, BEHAVIORS

mod = Module()


def _values(table: dict) -> list:
    return [
        {"id": name, "desc": v[1] if isinstance(v, tuple) else v}
        for name, v in table.items()
    ]


def types() -> dict:
    return {
        "easing": {
            "desc": "Easing curve, t from 0 to 1.",
            "values": _values(EASINGS),
        },
        "interpolation": {
            "desc": "How x and y blend from one value to the next.",
            "values": _values(INTERPOLATIONS),
        },
        "mode": {
            "desc": "How a layer combines with what's beneath it.",
            "values": _values(MODES),
        },
        "behavior": {
            "desc": "What a repeat does while the last is still running. Default: 'to' replaces, the rest stack.",
            "values": _values(BEHAVIORS),
        },
    }


@mod.action_class
class Actions:
    def rig_core_types() -> dict:
        """Named sets of values rigs take:
        {name: {"desc": str, "values": [{"id": str, "desc": str}]}}"""
        return types()
