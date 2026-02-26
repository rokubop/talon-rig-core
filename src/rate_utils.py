"""Rate-based timing calculations for transitions

Converts rate parameters (units/second, degrees/second, pixels/second)
into duration values for lifecycle transitions.

100% shared between all device rigs.
"""

from typing import Optional
import math

from .vec2 import Vec2, EPSILON


def calculate_duration_from_rate(
    value: float,
    rate: float,
    min_duration_ms: float = 1.0
) -> float:
    """Calculate duration in milliseconds from a value and rate.

    Args:
        value: The absolute value to transition (e.g., speed delta, rotation degrees)
        rate: The rate per second (e.g., units/second, degrees/second)
        min_duration_ms: Minimum duration to return

    Returns:
        Duration in milliseconds
    """
    if abs(value) < 0.01:
        return min_duration_ms
    duration_sec = abs(value) / rate
    return max(duration_sec * 1000, min_duration_ms)


def calculate_speed_duration(
    current: float,
    target: float,
    rate: float
) -> float:
    """Calculate duration for speed transition based on rate."""
    delta = abs(target - current)
    return calculate_duration_from_rate(delta, rate)


def calculate_direction_duration(
    current: Vec2,
    target: Vec2,
    rate: float
) -> float:
    """Calculate duration for direction rotation based on rate."""
    dot = current.dot(target)
    dot = max(-1.0, min(1.0, dot))
    angle_rad = math.acos(dot)
    angle_deg = math.degrees(angle_rad)
    return calculate_duration_from_rate(angle_deg, rate)


def calculate_direction_by_duration(
    angle_delta: float,
    rate: float
) -> float:
    """Calculate duration for relative direction rotation based on rate."""
    return calculate_duration_from_rate(abs(angle_delta), rate)


def calculate_position_duration(
    current: Vec2,
    target: Vec2,
    rate: float
) -> float:
    """Calculate duration for position movement based on rate."""
    delta = target - current
    distance = delta.magnitude()
    return calculate_duration_from_rate(distance, rate)


def calculate_position_by_duration(
    offset: Vec2,
    rate: float
) -> float:
    """Calculate duration for relative position movement based on rate."""
    distance = offset.magnitude()
    return calculate_duration_from_rate(distance, rate)


def calculate_vector_duration(
    current: Vec2,
    target: Vec2,
    speed_rate: float,
    direction_rate: float
) -> float:
    """Calculate duration for vector transition based on speed and direction rates."""
    speed_duration = calculate_speed_duration(current.magnitude(), target.magnitude(), speed_rate)
    direction_duration = calculate_direction_duration(current.normalized(), target.normalized(), direction_rate)
    return max(speed_duration, direction_duration)
