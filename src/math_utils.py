"""Math utilities shared between all device rigs"""

import math
from typing import Tuple

from .vec2 import EPSILON


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b"""
    return a + (b - a) * t


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))


def normalize_vector(x: float, y: float) -> Tuple[float, float]:
    """Normalize a 2D vector to unit length"""
    mag = math.sqrt(x ** 2 + y ** 2)
    if mag < EPSILON:
        return (0.0, 0.0)
    return (x / mag, y / mag)
