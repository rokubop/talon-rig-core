"""Mode operations - unified abstractions for offset/override/scale transformations

This module provides the core abstractions for how modes interact with operators:

Phase 1: Operator -> Canonical Value
    Convert user operator + value into the canonical form for the mode:
    - offset: contribution (additive delta)
    - override: absolute value
    - scale: multiplier

Phase 2: Canonical Value -> Application
    Apply the canonical value to accumulated state:
    - offset: accumulated + canonical
    - override: canonical
    - scale: accumulated * canonical

Shared between all device rigs.
"""

import math
from typing import Any, Union

from .vec2 import Vec2, EPSILON


# =============================================================================
# SCALAR OPERATIONS (speed, trigger, magnitude, numeric values)
# =============================================================================

def calculate_scalar_target(
    operator: str,
    value: float,
    current: float,
    mode: str
) -> float:
    """Convert operator + value to canonical form for mode.

    Args:
        operator: The operation (to, add, mul)
        value: The input value
        current: The current/base value
        mode: The mode (offset, override, scale)

    Returns:
        Canonical value for the mode
    """
    if mode == "scale":
        if operator == "to":
            return value
        elif operator in ("by", "add"):
            return 1.0 + value
        elif operator == "mul":
            return value

    elif mode == "override":
        if operator == "to":
            return value
        elif operator in ("by", "add"):
            return current + value
        elif operator == "mul":
            return current * value

    else:  # offset
        if operator == "to":
            return value
        elif operator in ("by", "add"):
            return value
        elif operator == "mul":
            return current * (value - 1)

    return value


def apply_scalar_mode(
    mode: str,
    canonical_value: float,
    accumulated: float
) -> float:
    """Apply canonical value to accumulated state based on mode."""
    if mode == "offset":
        return accumulated + canonical_value
    elif mode == "override":
        return canonical_value
    elif mode == "scale":
        return accumulated * canonical_value
    return accumulated


# =============================================================================
# DIRECTION OPERATIONS (vector normalization, rotation)
# =============================================================================

def calculate_direction_target(
    operator: str,
    value: Union[tuple, float],
    current: Vec2,
    mode: str
) -> Union[Vec2, float]:
    """Convert operator + value to canonical form for direction mode."""
    if mode == "scale":
        if operator == "to":
            return value
        elif operator in ("by", "add"):
            return 1.0 + value
        elif operator == "mul":
            return value

    elif mode == "override":
        if operator == "to":
            return Vec2.from_tuple(value).normalized()
        elif operator in ("by", "add"):
            if isinstance(value, tuple) and len(value) == 2:
                delta = Vec2.from_tuple(value)
                return (current + delta).normalized()
            else:
                angle_deg = value[0] if isinstance(value, tuple) else value
                angle_rad = math.radians(angle_deg)
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                new_x = current.x * cos_a - current.y * sin_a
                new_y = current.x * sin_a + current.y * cos_a
                return Vec2(new_x, new_y).normalized()
        elif operator == "mul":
            scalar = value[0] if isinstance(value, tuple) else value
            result = Vec2(current.x * scalar, current.y * scalar)
            return result.normalized() if scalar >= 0 else result

    else:  # offset
        if operator == "to":
            return Vec2.from_tuple(value).normalized()
        elif operator in ("by", "add"):
            if isinstance(value, tuple) and len(value) == 2:
                return Vec2.from_tuple(value)
            else:
                angle_deg = value[0] if isinstance(value, tuple) else value
                return angle_deg
    return current


def apply_direction_mode(
    mode: str,
    canonical_value: Union[Vec2, float],
    accumulated: Vec2
) -> Vec2:
    """Apply canonical value to accumulated direction based on mode."""
    if mode == "offset":
        if isinstance(canonical_value, (int, float)):
            angle_rad = math.radians(canonical_value)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            new_x = accumulated.x * cos_a - accumulated.y * sin_a
            new_y = accumulated.x * sin_a + accumulated.y * cos_a
            return Vec2(new_x, new_y).normalized()
        else:
            try:
                return (accumulated + canonical_value).normalized()
            except Exception:
                return canonical_value.normalized()

    elif mode == "override":
        return canonical_value

    elif mode == "scale":
        return Vec2(accumulated.x * canonical_value, accumulated.y * canonical_value).normalized()

    return accumulated


# =============================================================================
# POSITION OPERATIONS (2D vectors)
# =============================================================================

def calculate_position_target(
    operator: str,
    value: Union[tuple, 'Vec2'],
    current: Vec2,
    mode: str
) -> Union[Vec2, float]:
    """Convert operator + value to canonical form for position mode."""
    if mode == "scale":
        if operator == "to":
            return value
        elif operator in ("by", "add"):
            return 1.0 + value

    elif mode == "override":
        if operator == "to":
            return Vec2.from_tuple(value)
        elif operator in ("by", "add"):
            return current + Vec2.from_tuple(value)

    else:  # offset
        if operator == "to":
            desired_offset = Vec2.from_tuple(value)
            if current.x != 0 or current.y != 0:
                return desired_offset - current
            return desired_offset
        elif operator in ("by", "add"):
            desired_offset = Vec2.from_tuple(value)
            if current.x != 0 or current.y != 0:
                return desired_offset - current
            return desired_offset

    return current


def apply_position_mode(
    mode: str,
    canonical_value: Union[Vec2, float],
    accumulated: Vec2
) -> Vec2:
    """Apply canonical value to accumulated position based on mode."""
    if mode == "offset":
        return accumulated + canonical_value
    elif mode == "override":
        return canonical_value
    elif mode == "scale":
        return Vec2(accumulated.x * canonical_value, accumulated.y * canonical_value)
    return accumulated


# =============================================================================
# VECTOR OPERATIONS (velocity = speed + direction)
# =============================================================================

def calculate_vector_target(
    operator: str,
    value: Union[tuple, Vec2],
    current_speed: float,
    current_direction: Vec2,
    mode: str
) -> Vec2:
    """Convert operator + value to canonical form for vector mode."""
    vec = Vec2.from_tuple(value)

    if mode == "scale":
        if operator == "to":
            return Vec2(vec.magnitude(), 0)
        elif operator in ("by", "add"):
            return Vec2(1.0 + vec.magnitude(), 0)

    elif mode == "override":
        if operator == "to":
            return vec
        elif operator in ("by", "add"):
            current_velocity = current_direction * current_speed
            return current_velocity + vec

    else:  # offset
        if operator == "to":
            return vec
        elif operator in ("by", "add"):
            return vec

    return vec


def apply_vector_mode(
    mode: str,
    canonical_value: Vec2,
    accumulated_speed: float,
    accumulated_direction: Vec2
) -> tuple[float, Vec2]:
    """Apply canonical vector value to accumulated speed and direction.

    Returns:
        Tuple of (new_speed, new_direction)
    """
    if mode == "offset":
        accumulated_velocity = accumulated_direction * accumulated_speed
        new_velocity = accumulated_velocity + canonical_value

        speed = new_velocity.magnitude()
        if speed < EPSILON:
            direction = accumulated_direction
        else:
            direction = new_velocity.normalized()

        return speed, direction

    elif mode == "override":
        speed = canonical_value.magnitude()
        direction = canonical_value.normalized()
        return speed, direction

    elif mode == "scale":
        speed = accumulated_speed * canonical_value.magnitude()
        if speed < EPSILON:
            direction = accumulated_direction
        else:
            direction = (accumulated_direction * canonical_value.magnitude()).normalized()
        return speed, direction

    return accumulated_speed, accumulated_direction
