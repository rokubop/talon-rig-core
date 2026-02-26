"""PropertyKind system - four fundamental computational kinds for rig properties

All rig properties map to one of four kinds:

| Kind      | Type    | Neutral (offset) | Neutral (scale) | Examples                        |
|-----------|---------|-------------------|------------------|---------------------------------|
| SCALAR    | float   | 0.0               | 1.0              | speed, trigger, magnitude, x, y |
| POSITION  | Vec2    | Vec2(0,0)         | 1.0              | mouse pos, scroll pos           |
| DIRECTION | Vec2    | identity          | 1.0              | heading, stick direction         |
| VECTOR    | Vec2    | Vec2(0,0)         | 1.0              | velocity, stick deflection       |

Each kind determines:
- How to calculate targets (calculate_*_target)
- How to apply modes (apply_*_mode)
- How to animate (PropertyAnimator.animate_*)
- What the neutral/zero value is
"""

from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field

from .vec2 import Vec2


class PropertyKind(Enum):
    """Four fundamental computational kinds for rig properties"""
    SCALAR = "scalar"
    POSITION = "position"
    DIRECTION = "direction"
    VECTOR = "vector"


@dataclass
class PropertySchema:
    """Declares a property's kind and constraints.

    Device rigs use this to declare their properties:

    # Gamepad
    "left_stick": PropertySchema("left_stick", VECTOR, bounds=("circle", 1.0),
        decompositions={
            "direction": PropertySchema("direction", DIRECTION),
            "magnitude": PropertySchema("magnitude", SCALAR, bounds=(0, 1)),
            "x": PropertySchema("x", SCALAR, bounds=(-1, 1)),
            "y": PropertySchema("y", SCALAR, bounds=(-1, 1)),
        })
    "left_trigger": PropertySchema("left_trigger", SCALAR, bounds=(0, 1))

    # Mouse
    "pos": PropertySchema("pos", POSITION)
    "speed": PropertySchema("speed", SCALAR)
    "direction": PropertySchema("direction", DIRECTION)
    "vector": PropertySchema("vector", VECTOR)
    """
    name: str
    kind: PropertyKind
    bounds: Optional[Any] = None  # (min, max) for scalar, ("circle", radius) for position
    decompositions: Optional[dict[str, 'PropertySchema']] = field(default=None)

    def zero_value(self) -> Any:
        """Get zero/neutral value for offset mode"""
        if self.kind == PropertyKind.SCALAR:
            return 0.0
        elif self.kind == PropertyKind.POSITION:
            return Vec2(0, 0)
        elif self.kind == PropertyKind.DIRECTION:
            return Vec2(1, 0)  # Default direction (identity)
        elif self.kind == PropertyKind.VECTOR:
            return Vec2(0, 0)
        return 0.0

    def scale_neutral(self) -> float:
        """Get neutral value for scale mode (always 1.0)"""
        return 1.0


def zero_value_for_kind(kind: PropertyKind) -> Any:
    """Get zero/neutral value for a PropertyKind (offset mode)"""
    if kind == PropertyKind.SCALAR:
        return 0.0
    elif kind == PropertyKind.POSITION:
        return Vec2(0, 0)
    elif kind == PropertyKind.DIRECTION:
        return Vec2(1, 0)
    elif kind == PropertyKind.VECTOR:
        return Vec2(0, 0)
    return 0.0
