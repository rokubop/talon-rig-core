"""Easing functions for animation transitions

13 easing functions + registry. Shared between all device rigs.
"""

import math
from typing import Callable


def ease_linear(t: float) -> float:
    return t


def ease_in(t: float) -> float:
    return 1 - math.cos(t * math.pi / 2)


def ease_out(t: float) -> float:
    return math.sin(t * math.pi / 2)


def ease_in_out(t: float) -> float:
    return (1 - math.cos(t * math.pi)) / 2


def ease_in2(t: float) -> float:
    return t ** 2


def ease_out2(t: float) -> float:
    return 1 - (1 - t) ** 2


def ease_in_out2(t: float) -> float:
    return 2 * t ** 2 if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def ease_in3(t: float) -> float:
    return t ** 3


def ease_out3(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out3(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_in4(t: float) -> float:
    return t ** 4


def ease_out4(t: float) -> float:
    return 1 - (1 - t) ** 4


def ease_in_out4(t: float) -> float:
    return 8 * t ** 4 if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2


# name: (function, description)
EASINGS = {
    "linear": (ease_linear, "The same pace start to end."),
    "ease_in": (ease_in, "Starts slow and speeds up, on a sine curve."),
    "ease_out": (ease_out, "Starts fast and slows into the end, on a sine curve."),
    "ease_in_out": (ease_in_out, "Slow at both ends, fastest in the middle, on a sine curve."),
    "ease_in2": (ease_in2, "ease_in, sharper: a squared curve."),
    "ease_out2": (ease_out2, "ease_out, sharper: a squared curve."),
    "ease_in_out2": (ease_in_out2, "ease_in_out, sharper: a squared curve."),
    "ease_in3": (ease_in3, "ease_in, sharper again: a cubed curve."),
    "ease_out3": (ease_out3, "ease_out, sharper again: a cubed curve."),
    "ease_in_out3": (ease_in_out3, "ease_in_out, sharper again: a cubed curve."),
    "ease_in4": (ease_in4, "ease_in at its sharpest: a fourth-power curve."),
    "ease_out4": (ease_out4, "ease_out at its sharpest: a fourth-power curve."),
    "ease_in_out4": (ease_in_out4, "ease_in_out at its sharpest: a fourth-power curve."),
}

EASING_FUNCTIONS = {name: fn for name, (fn, _desc) in EASINGS.items()}


def get_easing_function(name: str) -> Callable[[float], float]:
    """Get easing function by name, defaults to linear"""
    return EASING_FUNCTIONS.get(name, ease_linear)
