"""PropertyAnimator - handles animation of property values during lifecycle phases

Extracted from lifecycle.py since it's 100% shared between all device rigs.
"""

import math
from typing import Optional

from .vec2 import Vec2, EPSILON
from .math_utils import lerp
from .contracts import LifecyclePhase


class PropertyAnimator:
    """Handles animation of property values during lifecycle phases"""

    @staticmethod
    def animate_scalar(
        base_value: float,
        target_value: float,
        phase: Optional[str],
        progress: float,
        has_reverted: bool = False
    ) -> float:
        """Animate a scalar property value.

        Args:
            base_value: The neutral/starting value (depends on mode: 0 for offset, 1 for scale, base for override)
            target_value: The target value to animate to
            phase: Current lifecycle phase
            progress: Progress [0, 1] within current phase
            has_reverted: Whether this lifecycle completed via revert

        Returns:
            Current animated value
        """
        if phase is None:
            if has_reverted:
                return base_value
            return target_value

        if phase == LifecyclePhase.OVER:
            return lerp(base_value, target_value, progress)
        elif phase == LifecyclePhase.HOLD:
            return target_value
        elif phase == LifecyclePhase.REVERT:
            return lerp(target_value, base_value, progress)

        return target_value

    @staticmethod
    def animate_direction(
        base_dir: Vec2,
        target_dir: Vec2,
        phase: Optional[str],
        progress: float,
        has_reverted: bool = False,
        interpolation: str = "lerp"
    ) -> Vec2:
        """Animate a direction vector using lerp, slerp, or linear.

        Args:
            base_dir: The base direction vector (normalized)
            target_dir: The target direction vector (normalized)
            phase: Current lifecycle phase
            progress: Progress [0, 1] within current phase
            has_reverted: Whether this lifecycle completed via revert
            interpolation: "lerp" for linear interpolation, "slerp" for spherical,
                          or "linear" for component-wise (no normalization, for reversals)

        Returns:
            Current animated direction vector
        """
        if phase is None:
            if has_reverted:
                return base_dir
            return target_dir

        if phase == LifecyclePhase.OVER:
            if interpolation == "linear":
                x = base_dir.x + (target_dir.x - base_dir.x) * progress
                y = base_dir.y + (target_dir.y - base_dir.y) * progress
                return Vec2(x, y)
            elif interpolation == "slerp":
                return _slerp(base_dir, target_dir, progress)
            else:
                return _lerp_direction(base_dir, target_dir, progress)
        elif phase == LifecyclePhase.HOLD:
            return target_dir
        elif phase == LifecyclePhase.REVERT:
            if interpolation == "linear":
                x = target_dir.x + (base_dir.x - target_dir.x) * progress
                y = target_dir.y + (base_dir.y - target_dir.y) * progress
                return Vec2(x, y)
            elif interpolation == "slerp":
                return _slerp(target_dir, base_dir, progress)
            else:
                return _lerp_direction(target_dir, base_dir, progress)

        return target_dir

    @staticmethod
    def animate_position(
        base_pos: Vec2,
        target_offset: Vec2,
        phase: Optional[str],
        progress: float,
        has_reverted: bool = False
    ) -> Vec2:
        """Animate a position offset.

        Args:
            base_pos: The base position
            target_offset: The target offset from base
            phase: Current lifecycle phase
            progress: Progress [0, 1] within current phase
            has_reverted: Whether this lifecycle completed via revert

        Returns:
            Current offset to apply
        """
        if phase is None:
            if has_reverted:
                return Vec2(0, 0)
            return target_offset

        if phase == LifecyclePhase.OVER:
            return target_offset * progress
        elif phase == LifecyclePhase.HOLD:
            return target_offset
        elif phase == LifecyclePhase.REVERT:
            return target_offset * (1.0 - progress)

        return target_offset

    @staticmethod
    def animate_vector(
        base_vector: Vec2,
        target_vector: Vec2,
        phase: Optional[str],
        progress: float,
        has_reverted: bool = False,
        interpolation: str = 'lerp'
    ) -> Vec2:
        """Animate a velocity vector (speed + direction combined).

        Args:
            base_vector: The base velocity vector
            target_vector: The target velocity vector
            phase: Optional[str]
            progress: Progress [0, 1] within current phase
            has_reverted: Whether this lifecycle completed via revert
            interpolation: 'lerp' for magnitude/direction, 'linear' for component-wise

        Returns:
            Current animated velocity vector
        """
        if phase is None:
            if has_reverted:
                return base_vector
            return target_vector

        if phase == LifecyclePhase.OVER:
            if interpolation == 'linear':
                x = base_vector.x + (target_vector.x - base_vector.x) * progress
                y = base_vector.y + (target_vector.y - base_vector.y) * progress
                return Vec2(x, y)
            base_speed = base_vector.magnitude()
            target_speed = target_vector.magnitude()
            interpolated_speed = lerp(base_speed, target_speed, progress)

            if base_speed < EPSILON and target_speed < EPSILON:
                return Vec2(0, 0)
            elif base_speed < EPSILON:
                return target_vector.normalized() * interpolated_speed
            elif target_speed < EPSILON:
                return base_vector.normalized() * (base_speed * (1.0 - progress))

            base_dir = base_vector.normalized()
            target_dir = target_vector.normalized()
            interpolated_dir = _lerp_direction(base_dir, target_dir, progress)

            return interpolated_dir * interpolated_speed

        elif phase == LifecyclePhase.HOLD:
            return target_vector

        elif phase == LifecyclePhase.REVERT:
            if interpolation == 'linear':
                x = target_vector.x + (base_vector.x - target_vector.x) * progress
                y = target_vector.y + (base_vector.y - target_vector.y) * progress
                return Vec2(x, y)

            base_speed = base_vector.magnitude()
            target_speed = target_vector.magnitude()
            interpolated_speed = lerp(target_speed, base_speed, progress)

            if base_speed < EPSILON and target_speed < EPSILON:
                return Vec2(0, 0)
            elif base_speed < EPSILON:
                return target_vector.normalized() * (target_speed * (1.0 - progress))
            elif target_speed < EPSILON:
                return base_vector.normalized() * interpolated_speed

            base_dir = base_vector.normalized()
            target_dir = target_vector.normalized()
            interpolated_dir = _lerp_direction(target_dir, base_dir, progress)

            return interpolated_dir * interpolated_speed

        return target_vector


def _lerp_direction(v1: Vec2, v2: Vec2, t: float) -> Vec2:
    """Linear interpolation between two direction vectors"""
    x = v1.x + (v2.x - v1.x) * t
    y = v1.y + (v2.y - v1.y) * t
    return Vec2(x, y).normalized()


def _slerp(v1: Vec2, v2: Vec2, t: float) -> Vec2:
    """Spherical linear interpolation between two direction vectors"""
    dot = v1.dot(v2)
    dot = max(-1.0, min(1.0, dot))
    angle = math.acos(dot)

    if angle < EPSILON:
        return v2

    cross = v1.x * v2.y - v1.y * v2.x
    direction = 1 if cross >= 0 else -1

    current_angle = angle * t * direction
    cos_a = math.cos(current_angle)
    sin_a = math.sin(current_angle)

    new_x = v1.x * cos_a - v1.y * sin_a
    new_y = v1.x * sin_a + v1.y * cos_a

    return Vec2(new_x, new_y).normalized()


def calculate_vector_transition(
    current: Vec2,
    target: Vec2,
    progress: float
) -> Vec2:
    """Calculate the interpolated vector value during a transition."""
    interpolated_speed = lerp(current.magnitude(), target.magnitude(), progress)
    interpolated_direction = _lerp_direction(current.normalized(), target.normalized(), progress)

    return interpolated_direction * interpolated_speed
