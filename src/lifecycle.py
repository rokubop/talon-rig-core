"""Lifecycle management for builder transitions (over/hold/revert phases)

Handles the temporal aspects of builders:
- Over: Transition from current to target value
- Hold: Sustain the target value
- Revert: Transition back to original value

100% shared between all device rigs.
"""

import time
from typing import Optional, Callable, Any

from .easing import get_easing_function
from .contracts import LifecyclePhase


class Lifecycle:
    """Manages the over/hold/revert lifecycle for a builder"""

    def __init__(self, is_modifier_layer: bool = False):
        self.over_ms: Optional[float] = None
        self.over_easing: str = "linear"
        self.hold_ms: Optional[float] = None
        self.revert_ms: Optional[float] = None
        self.revert_easing: str = "linear"

        self.is_modifier_layer = is_modifier_layer

        self.callbacks: dict[str, list[Callable]] = {
            LifecyclePhase.OVER: [],
            LifecyclePhase.HOLD: [],
            LifecyclePhase.REVERT: [],
        }

        self.phase: Optional[str] = None
        self.phase_start_time: Optional[float] = None
        self.started = False

    def add_callback(self, phase: str, callback: Callable):
        if phase not in self.callbacks:
            self.callbacks[phase] = []
        self.callbacks[phase].append(callback)

    def start(self, current_time: float):
        """Start the lifecycle"""
        self.started = True
        self.phase_start_time = current_time

        if self.over_ms is not None and self.over_ms > 0:
            self.phase = LifecyclePhase.OVER
        elif self.hold_ms is not None and self.hold_ms > 0:
            self.phase = LifecyclePhase.HOLD
        elif self.revert_ms is not None and self.revert_ms > 0:
            self.phase = LifecyclePhase.REVERT
        else:
            self.phase = LifecyclePhase.OVER

    def advance(self, current_time: float) -> tuple[Optional[str], float]:
        """Advance lifecycle state forward in time.

        Returns:
            (current_phase, progress) where progress is [0, 1] with easing applied
            Returns (None, 1.0) if lifecycle is complete
        """
        if not self.started:
            self.start(current_time)

        if self.phase is None:
            return (None, 1.0)

        elapsed = (current_time - self.phase_start_time) * 1000

        if self.phase == LifecyclePhase.OVER:
            if self.over_ms is None or self.over_ms == 0:
                progress = 1.0
            else:
                progress = min(1.0, elapsed / self.over_ms)
                easing_fn = get_easing_function(self.over_easing)
                progress = easing_fn(progress)

            if elapsed >= (self.over_ms or 0):
                self._advance_to_next_phase(current_time)
                return self.advance(current_time)

            return (LifecyclePhase.OVER, progress)

        elif self.phase == LifecyclePhase.HOLD:
            if self.hold_ms is None or self.hold_ms == 0:
                progress = 1.0
            else:
                progress = 1.0

            if elapsed >= (self.hold_ms or 0):
                self._advance_to_next_phase(current_time)
                return self.advance(current_time)

            return (LifecyclePhase.HOLD, progress)

        elif self.phase == LifecyclePhase.REVERT:
            if self.revert_ms is None or self.revert_ms == 0:
                progress = 1.0
            else:
                progress = min(1.0, elapsed / self.revert_ms)
                easing_fn = get_easing_function(self.revert_easing)
                progress = easing_fn(progress)

            if elapsed >= (self.revert_ms or 0):
                self.phase = None
                return (None, 1.0)

            return (LifecyclePhase.REVERT, progress)

        return (None, 1.0)

    def _advance_to_next_phase(self, current_time: float):
        """Move to the next lifecycle phase"""
        self.phase_start_time = current_time

        if self.phase == LifecyclePhase.OVER:
            if self.hold_ms is not None and self.hold_ms > 0:
                self.phase = LifecyclePhase.HOLD
            elif self.revert_ms is not None and self.revert_ms > 0:
                self.phase = LifecyclePhase.REVERT
            else:
                self.phase = None

        elif self.phase == LifecyclePhase.HOLD:
            if self.revert_ms is not None and self.revert_ms > 0:
                self.phase = LifecyclePhase.REVERT
            else:
                self.phase = None

        elif self.phase == LifecyclePhase.REVERT:
            self.phase = None

    def get_phase_callbacks(self, phase: str) -> list:
        return self.callbacks.get(phase, [])

    def execute_callbacks(self, phase: str):
        for callback in self.callbacks.get(phase, []):
            try:
                callback()
            except Exception as e:
                print(f"Error in lifecycle callback: {e}")

    def is_complete(self) -> bool:
        if not self.has_any_lifecycle():
            return True
        return self.started and self.phase is None

    def has_any_lifecycle(self) -> bool:
        return (
            (self.over_ms is not None and self.over_ms > 0) or
            (self.hold_ms is not None and self.hold_ms > 0) or
            (self.revert_ms is not None and self.revert_ms >= 0)
        )

    def is_reverting(self) -> bool:
        return self.phase == LifecyclePhase.REVERT

    def has_reverted(self) -> bool:
        """Check if this lifecycle completed with a revert phase

        Only returns True if revert_ms was explicitly set (meaning .revert() was called).
        Builders with only .over() or .hold() should still bake.
        """
        return (
            self.started and
            self.phase is None and
            self.revert_ms is not None and
            self.revert_ms >= 0
        )

    def trigger_revert(self, current_time: float, revert_ms: Optional[float] = None, easing: str = "linear"):
        """Externally trigger the revert phase, interrupting whatever phase is active."""
        if revert_ms is not None:
            self.revert_ms = revert_ms
        if easing:
            self.revert_easing = easing

        if not self.revert_ms or self.revert_ms <= 0:
            self.revert_ms = 0
            self.phase = None
            return

        self.phase = LifecyclePhase.REVERT
        self.phase_start_time = current_time

    def is_animating(self) -> bool:
        """Check if lifecycle is currently in an active animation phase."""
        return self.phase in (LifecyclePhase.OVER, LifecyclePhase.REVERT)

    def should_be_garbage_collected(self) -> bool:
        """Check if builder should be removed from active builders.

        Garbage collection rules:
        - Anonymous builders: removed when lifecycle completes
        - Named builders: removed only when explicitly reverted
        - Any builder: removed if reverted (regardless of named/anonymous)
        """
        if not self.is_complete():
            return False

        if self.has_reverted():
            return True

        if not self.is_modifier_layer:
            return True

        return False
