"""BaseActiveBuilder - Abstract base class for active builders being executed

Provides shared lifecycle management, value resolution, and interpolation dispatch.
Device rigs implement 3 abstract methods for device-specific value access.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, Any, TYPE_CHECKING

from .vec2 import Vec2, is_vec2
from .contracts import BaseBuilderConfig, LifecyclePhase, LayerType
from .lifecycle import Lifecycle
from .property_animator import PropertyAnimator
from .property_kind import PropertyKind
from . import mode_operations

if TYPE_CHECKING:
    from .state import BaseRigState
    from .layer_group import BaseLayerGroup


class BaseActiveBuilder(ABC):
    """An active builder being executed in the state manager.

    Concrete methods:
    - __init__ — lifecycle setup, callbacks, calls abstract hooks
    - _resolve_base_value() — template method (to->current_or_base, by/add->base for modifiers)
    - _get_current_or_base_value() — check group for mid-animation value
    - advance(current_time) — advance lifecycle
    - _get_own_value() — interpolation dispatch by PropertyKind
    - get_interpolated_value() — public interpolated value

    Abstract methods (3):
    - _get_base_value() — read raw base from device state
    - _calculate_target_value() — compute target via mode_operations
    - _get_property_kind() — return PropertyKind for animation routing
    """

    def __init__(self, config: BaseBuilderConfig, rig_state: 'BaseRigState', is_base_layer: bool):
        self.config = config
        self.rig_state = rig_state
        self.is_base_layer = is_base_layer
        self.layer = config.layer_name
        self.creation_time = time.perf_counter()

        # Back-reference to containing group (set by BaseLayerGroup.add_builder)
        self.group: Optional['BaseLayerGroup'] = None

        # For base layers, always use override mode to store absolute result values
        if config.mode is None:
            config.mode = "override"

        self.group_lifecycle: Optional[Lifecycle] = None
        self.group_base_value: Optional[Any] = None
        self.group_target_value: Optional[Any] = None

        self._marked_for_removal: bool = False

        self.lifecycle = Lifecycle(is_modifier_layer=not is_base_layer)
        self.lifecycle.over_ms = config.over_ms
        self.lifecycle.over_easing = config.over_easing
        self.lifecycle.hold_ms = config.hold_ms
        self.lifecycle.revert_ms = config.revert_ms
        self.lifecycle.revert_easing = config.revert_easing

        for stage, callback in config.then_callbacks:
            self.lifecycle.add_callback(stage, callback)

        # Resolve base value using template method
        self.base_value = self._resolve_base_value()
        self.target_value = self._calculate_target_value()

        # Revert target (set by state manager for offset mode with replace)
        self.revert_target: Optional[Any] = None

    def _resolve_base_value(self) -> Any:
        """Template method: resolve base value based on operator and layer type.

        - to: use current animated value (bakes current state before transitioning)
        - by/add: base layers use current animated, modifier layers use raw base
        - other: same as by/add
        """
        if self.config.operator == "to":
            return self._get_current_or_base_value()
        elif self.config.operator in ("by", "add"):
            if self.is_base_layer:
                return self._get_current_or_base_value()
            else:
                return self._get_base_value()
        else:
            if self.is_base_layer:
                return self._get_current_or_base_value()
            else:
                return self._get_base_value()

    def _get_current_or_base_value(self) -> Any:
        """Get current animated value if mid-transition, otherwise base value."""
        layer = self.config.layer_name
        if layer in self.rig_state._layer_groups:
            group = self.rig_state._layer_groups[layer]
            if group.is_base and group.builders:
                value = group.get_current_value()
                if value is not None:
                    return value
        return self._get_base_value()

    @property
    def time_alive(self) -> float:
        """Get time in seconds since this builder was created"""
        return time.perf_counter() - self.creation_time

    def advance(self, current_time: float) -> tuple[str, list]:
        """Advance this builder forward in time."""
        phase_transitions = []

        if self.group_lifecycle:
            self.group_lifecycle.advance(current_time)
            if self.group_lifecycle.is_complete():
                if self.group_lifecycle.has_reverted():
                    self._marked_for_removal = True
                self.group_lifecycle = None
                return (None, [])

        old_phase = self.lifecycle.phase
        self.lifecycle.advance(current_time)
        new_phase = self.lifecycle.phase

        if old_phase != new_phase and old_phase is not None:
            phase_transitions.append((self, old_phase))

        return (old_phase if old_phase != new_phase else None, phase_transitions)

    def _get_own_value(self) -> Any:
        """Get this builder's own interpolated value, dispatched by PropertyKind."""
        current_time = time.perf_counter()
        phase, progress = self.lifecycle.advance(current_time)
        mode = self.config.mode
        kind = self._get_property_kind()

        if kind == PropertyKind.SCALAR:
            if mode == "scale":
                neutral = 1.0
            elif mode == "offset":
                neutral = 0.0
            else:  # override
                neutral = self.base_value

            return PropertyAnimator.animate_scalar(
                neutral,
                self.target_value,
                phase,
                progress,
                self.lifecycle.has_reverted()
            )

        elif kind == PropertyKind.DIRECTION:
            interpolation = self.config.over_interpolation
            if phase == LifecyclePhase.REVERT:
                interpolation = self.config.revert_interpolation

            if mode == "offset":
                if isinstance(self.target_value, (int, float)):
                    # Animate angle from 0 to target angle
                    return PropertyAnimator.animate_scalar(
                        0.0,
                        self.target_value,
                        phase,
                        progress,
                        self.lifecycle.has_reverted()
                    )
                else:
                    return PropertyAnimator.animate_direction(
                        self.base_value,
                        self.target_value,
                        phase,
                        progress,
                        self.lifecycle.has_reverted(),
                        interpolation
                    )
            elif mode == "scale":
                return PropertyAnimator.animate_scalar(
                    1.0,
                    self.target_value,
                    phase,
                    progress,
                    self.lifecycle.has_reverted()
                )
            else:  # override
                return PropertyAnimator.animate_direction(
                    self.base_value,
                    self.target_value,
                    phase,
                    progress,
                    self.lifecycle.has_reverted(),
                    interpolation
                )

        elif kind == PropertyKind.POSITION:
            if mode == "scale":
                return PropertyAnimator.animate_scalar(
                    1.0,
                    self.target_value,
                    phase,
                    progress,
                    self.lifecycle.has_reverted()
                )
            elif mode == "offset":
                neutral = Vec2(0, 0)
                if phase is None:
                    if self.lifecycle.has_reverted():
                        return self.revert_target if self.revert_target is not None else neutral
                    return self.target_value
                elif phase == LifecyclePhase.OVER:
                    return self.target_value * progress
                elif phase == LifecyclePhase.HOLD:
                    return self.target_value
                elif phase == LifecyclePhase.REVERT:
                    revert_to = self.revert_target if self.revert_target is not None else neutral
                    return self.target_value + (revert_to - self.target_value) * progress
            else:  # override
                if phase is None:
                    if self.lifecycle.has_reverted():
                        return self.base_value
                    return self.target_value
                elif phase == LifecyclePhase.OVER:
                    return Vec2(
                        self.base_value.x + (self.target_value.x - self.base_value.x) * progress,
                        self.base_value.y + (self.target_value.y - self.base_value.y) * progress
                    )
                elif phase == LifecyclePhase.HOLD:
                    return self.target_value
                elif phase == LifecyclePhase.REVERT:
                    return Vec2(
                        self.target_value.x + (self.base_value.x - self.target_value.x) * progress,
                        self.target_value.y + (self.base_value.y - self.target_value.y) * progress
                    )

        elif kind == PropertyKind.VECTOR:
            if mode == "scale":
                return PropertyAnimator.animate_scalar(
                    1.0,
                    self.target_value.x if is_vec2(self.target_value) else self.target_value,
                    phase,
                    progress,
                    self.lifecycle.has_reverted()
                )
            elif mode == "offset":
                neutral = Vec2(0, 0)
                interpolation = self.config.over_interpolation
                return PropertyAnimator.animate_vector(
                    neutral,
                    self.target_value,
                    phase,
                    progress,
                    self.lifecycle.has_reverted(),
                    interpolation
                )
            else:  # override
                interpolation = self.config.over_interpolation
                return PropertyAnimator.animate_vector(
                    self.base_value,
                    self.target_value,
                    phase,
                    progress,
                    self.lifecycle.has_reverted(),
                    interpolation
                )

        return self.target_value

    def get_interpolated_value(self) -> Any:
        """Get current interpolated value for this builder"""
        if self.group_lifecycle and not self.group_lifecycle.is_complete():
            current_time = time.perf_counter()
            phase, progress = self.group_lifecycle.advance(current_time)

            kind = self._get_property_kind()
            interpolation = self.config.revert_interpolation

            if kind == PropertyKind.SCALAR:
                return PropertyAnimator.animate_scalar(
                    self.group_base_value,
                    self.group_target_value,
                    phase,
                    progress,
                    self.group_lifecycle.has_reverted()
                )
            elif kind == PropertyKind.DIRECTION:
                return PropertyAnimator.animate_direction(
                    self.group_base_value,
                    self.group_target_value,
                    phase,
                    progress,
                    self.group_lifecycle.has_reverted(),
                    interpolation
                )
            elif kind == PropertyKind.POSITION:
                return PropertyAnimator.animate_position(
                    self.group_base_value,
                    self.group_target_value,
                    phase,
                    progress,
                    self.group_lifecycle.has_reverted()
                )
            elif kind == PropertyKind.VECTOR:
                return PropertyAnimator.animate_vector(
                    self.group_base_value,
                    self.group_target_value,
                    phase,
                    progress,
                    self.group_lifecycle.has_reverted(),
                    interpolation
                )

        return self._get_own_value()

    def __repr__(self) -> str:
        phase = self.lifecycle.phase if self.lifecycle and self.lifecycle.phase else "instant"
        return f"<{self.__class__.__name__} '{self.layer}' {self.config.property}.{self.config.operator}({self.target_value}) mode={self.config.mode} phase={phase}>"

    def __str__(self) -> str:
        return self.__repr__()

    # ========================================================================
    # UTILITY METHODS (shared by device rigs)
    # ========================================================================

    def _is_same_axis_reversal(self, base_val, target_val) -> bool:
        """Detect same-axis 180° reversal between two Vec2 values.

        Returns True when both vectors are on the same axis (one component ~0)
        and pointing in opposite directions (dot product < -0.9).

        Used by device builders to auto-switch interpolation to 'linear'
        for smooth zero-crossing during direction reversals.
        """
        if not is_vec2(base_val) or not is_vec2(target_val):
            return False

        base_x_zero = abs(base_val.x) < 0.01
        base_y_zero = abs(base_val.y) < 0.01
        target_x_zero = abs(target_val.x) < 0.01
        target_y_zero = abs(target_val.y) < 0.01

        base_norm = base_val.normalized()
        target_norm = target_val.normalized()
        opposite_direction = base_norm.dot(target_norm) < -0.9

        return ((base_x_zero and target_x_zero) or (base_y_zero and target_y_zero)) and opposite_direction

    # ========================================================================
    # ABSTRACT METHODS (3 — device rigs implement)
    # ========================================================================

    @abstractmethod
    def _get_base_value(self) -> Any:
        """Read raw base value from device state for this property."""
        ...

    @abstractmethod
    def _calculate_target_value(self) -> Any:
        """Compute target value after operator is applied via mode_operations."""
        ...

    @abstractmethod
    def _get_property_kind(self) -> PropertyKind:
        """Return PropertyKind for this builder's property (for animation routing)."""
        ...
