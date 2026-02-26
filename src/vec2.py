"""Vec2 class for 2D vectors

Shared between all device rigs for direction, position, and velocity calculations.
"""

import math
from typing import Tuple, Union, Optional
from dataclasses import dataclass

# Small value for floating point comparisons (avoid division by zero, etc.)
EPSILON = 1e-10


def is_vec2(obj) -> bool:
    """Check if an object is a Vec2-like value (duck typing).
    Uses duck typing instead of isinstance to survive Talon hot-reloading,
    which can cause class identity mismatches between module reload cycles.
    """
    return hasattr(obj, 'x') and hasattr(obj, 'y') and not hasattr(obj, 'z')


@dataclass
class Vec2:
    """2D vector"""
    x: float
    y: float

    def __repr__(self) -> str:
        return f"Vec2({self.x:.2f}, {self.y:.2f})"

    def __str__(self) -> str:
        return f"({self.x:.2f}, {self.y:.2f})"

    def __add__(self, other: 'Vec2') -> 'Vec2':
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vec2') -> 'Vec2':
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> 'Vec2':
        return Vec2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> 'Vec2':
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> 'Vec2':
        return Vec2(self.x / scalar, self.y / scalar)

    def __neg__(self) -> 'Vec2':
        return Vec2(-self.x, -self.y)

    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalized(self) -> 'Vec2':
        mag = self.magnitude()
        if mag < EPSILON:
            return Vec2(0, 0)
        return Vec2(self.x / mag, self.y / mag)

    def dot(self, other: 'Vec2') -> float:
        return self.x * other.x + self.y * other.y

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def copy(self) -> 'Vec2':
        """Return a copy of this vector"""
        return Vec2(self.x, self.y)

    def clamped(self, min_val: float, max_val: float) -> 'Vec2':
        """Clamp each component independently"""
        return Vec2(
            max(min_val, min(max_val, self.x)),
            max(min_val, min(max_val, self.y))
        )

    def clamped_magnitude(self, max_mag: float) -> 'Vec2':
        """Clamp magnitude (preserving direction)"""
        mag = self.magnitude()
        if mag <= max_mag or mag < EPSILON:
            return Vec2(self.x, self.y)
        scale = max_mag / mag
        return Vec2(self.x * scale, self.y * scale)

    def to_cardinal(self) -> Optional[str]:
        """Convert vector to cardinal/intercardinal direction string

        Returns one of: "right", "left", "up", "down",
                       "up_right", "up_left", "down_right", "down_left"
        or None if vector is zero.
        """
        if self.x == 0 and self.y == 0:
            return None

        threshold = 2.414

        if abs(self.x) > abs(self.y) * threshold:
            return "right" if self.x > 0 else "left"
        if abs(self.y) > abs(self.x) * threshold:
            return "up" if self.y < 0 else "down"

        if self.x > 0 and self.y < 0:
            return "up_right"
        elif self.x < 0 and self.y < 0:
            return "up_left"
        elif self.x > 0 and self.y > 0:
            return "down_right"
        elif self.x < 0 and self.y > 0:
            return "down_left"

        return "right"

    @staticmethod
    def from_tuple(t: Union[Tuple[float, float], 'Vec2']) -> 'Vec2':
        if is_vec2(t):
            return Vec2(t.x, t.y)
        return Vec2(t[0], t[1])
