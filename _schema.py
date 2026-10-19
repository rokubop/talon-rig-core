"""
Provides user.rig_core_schema(): schema.json, what this package accepts
beyond its actions' signatures, as JSON Schema. A param or setting
that takes one of its sets says so in its docstring or desc:
`Type: rig_core.<name>`.
"""
import copy
import json
from pathlib import Path
from talon import Module

mod = Module()

SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text(encoding="utf-8"))


def ids(name: str) -> list:
    """A $defs entry's values in order: its oneOf consts, or those of
    the oneOf inside its anyOf."""
    entry = SCHEMA["$defs"][name]
    choices = entry.get("oneOf") or next(
        (a["oneOf"] for a in entry.get("anyOf", []) if "oneOf" in a), [])
    return [c["const"] for c in choices if "const" in c]


@mod.action_class
class Actions:
    def rig_core_schema() -> dict:
        """Named sets of values rigs accept, each described: easings,
        interpolations, layer modes and behaviors."""
        return copy.deepcopy(SCHEMA)
