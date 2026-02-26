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


EASING_FUNCTIONS = {
    "linear": ease_linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "ease_in2": ease_in2,
    "ease_out2": ease_out2,
    "ease_in_out2": ease_in_out2,
    "ease_in3": ease_in3,
    "ease_out3": ease_out3,
    "ease_in_out3": ease_in_out3,
    "ease_in4": ease_in4,
    "ease_out4": ease_out4,
    "ease_in_out4": ease_in_out4,
}


def get_easing_function(name: str) -> Callable[[float], float]:
    """Get easing function by name, defaults to linear"""
    return EASING_FUNCTIONS.get(name, ease_linear)
