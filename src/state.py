"""BaseRigState - Abstract base class for device rig state managers

Provides all shared behavior methods (throttle, debounce, queue, stack, replace),
frame loop management, builder lifecycle, and layer tracking.

Device rigs implement 8 abstract methods for device-specific behavior.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, Any, Union, TYPE_CHECKING

from .vec2 import Vec2, is_vec2, EPSILON
from .lifecycle import Lifecycle
from .property_kind import PropertyKind, zero_value_for_kind, identity_value_for_kind
from .contracts import (
    BaseBuilderConfig,
    LifecyclePhase,
    LayerType,
    ConfigError,
    validate_timing,
)
from . import mode_operations

if TYPE_CHECKING:
    from .builder import BaseActiveBuilder
    from .layer_group import BaseLayerGroup


class BaseRigState(ABC):
    """Abstract base class for device rig state managers.

    Concrete methods (100% shared):
    - Key helpers: _get_queue_key, _get_throttle_key, _get_rate_cache_key, _get_debounce_key
    - All behaviors: _apply_throttle_behavior, _apply_debounce_behavior,
      _check_and_update_rate_cache, _apply_stack_behavior, _apply_queue_behavior,
      _apply_replace_behavior
    - Frame loop: _ensure_frame_loop_running, _stop_frame_loop,
      _stop_frame_loop_if_done, _should_frame_loop_be_active, _calculate_delta_time
    - Builder mgmt: add_builder, _advance_all_builders, _remove_completed_builders,
      _execute_phase_callbacks, _check_debounce_pending
    - Layer utilities: _targets_match, _clear_layer_tracking, trigger_revert

    Abstract methods (9 - device rigs implement):
    - bake_all() - flatten all layers into base state
    - _get_or_create_group(builder) - init accumulated value from device base state
    - _compute_current_state() - apply all layers to base, return device tuple
    - _apply_group(group, *accumulated) - apply single group to accumulated state
    - _tick_frame() - frame body (advance + compute output + emit to hardware)
    - _bake_group_to_base(group) - write group value to base state fields
    - _bake_property(property_name, layer) - bake computed value into base
    - stop(transition_ms, easing) - stop all activity
    - _create_active_builder(config, is_base) - factory for device-specific ActiveBuilder
    """

    def __init__(self):
        # Layer groups (layer_name -> BaseLayerGroup)
        self._layer_groups: dict[str, 'BaseLayerGroup'] = {}

        # Layer order tracking
        self._layer_orders: dict[str, int] = {}

        # Frame loop
        self._frame_loop_job: Optional[Any] = None
        self._last_frame_time: Optional[float] = None

        # Throttle tracking (global - spans group recreation)
        self._throttle_times: dict[str, float] = {}

        # Auto-order counter for layers without explicit order
        self._next_auto_order: int = 0

        # Rate-based builder cache (cache_key -> (builder, target_value))
        self._rate_builder_cache: dict[tuple, tuple['BaseActiveBuilder', Any]] = {}

        # Debounce pending builders
        self._debounce_pending: dict[str, tuple[float, 'BaseBuilderConfig', bool, Optional[Any]]] = {}

        # Stop callbacks (fired when frame loop stops)
        self._stop_callbacks: list = []

    # ========================================================================
    # KEY HELPERS (100% shared)
    # ========================================================================

    def _get_queue_key(self, layer: str, builder: 'BaseActiveBuilder') -> str:
        """Get the queue key for a builder"""
        return f"{layer}_{builder.config.property}_{builder.config.operator}"

    def _get_throttle_key(self, layer: str, builder_or_config: Union['BaseActiveBuilder', 'BaseBuilderConfig']) -> str:
        """Get throttle key for a builder"""
        config = builder_or_config if isinstance(builder_or_config, BaseBuilderConfig) else builder_or_config.config
        return f"{layer}_{config.property}_{config.operator}"

    def _get_rate_cache_key(self, layer: str, config: 'BaseBuilderConfig') -> Optional[tuple]:
        """Get rate cache key for a builder using rate-based timing"""
        if config.over_rate is None and config.revert_rate is None:
            return None

        target = config.value
        if isinstance(target, tuple):
            normalized = tuple(round(v, 3) for v in target)
        elif isinstance(target, (int, float)):
            normalized = round(target, 3)
        else:
            normalized = target

        return (layer, config.property, config.operator, config.mode, normalized)

    def _get_debounce_key(self, layer: str, config: 'BaseBuilderConfig') -> str:
        """Get debounce key for a builder"""
        return f"{layer}_{config.property}_{config.operator}"

    # ========================================================================
    # LAYER TRACKING (100% shared)
    # ========================================================================

    def _clear_layer_tracking(self, layers: list[str]):
        """Clean up throttle, rate cache, and debounce entries for given layers"""
        for layer in layers:
            group = self._layer_groups.get(layer)
            if group is None:
                continue
            for builder in group.builders:
                rate_cache_key = self._get_rate_cache_key(layer, builder.config)
                if rate_cache_key is not None and rate_cache_key in self._rate_builder_cache:
                    del self._rate_builder_cache[rate_cache_key]

                throttle_key = self._get_throttle_key(layer, builder)
                if throttle_key in self._throttle_times:
                    del self._throttle_times[throttle_key]

                debounce_key = self._get_debounce_key(layer, builder.config)
                if debounce_key in self._debounce_pending:
                    _, _, _, cron_job = self._debounce_pending[debounce_key]
                    if cron_job is not None:
                        self._cancel_cron(cron_job)
                    del self._debounce_pending[debounce_key]

    def _targets_match(self, target1: Any, target2: Any) -> bool:
        """Check if two target values match (with epsilon for floats)"""
        if isinstance(target1, (int, float)) and isinstance(target2, (int, float)):
            return abs(target1 - target2) < EPSILON
        elif isinstance(target1, tuple) and isinstance(target2, tuple):
            return all(abs(a - b) < EPSILON for a, b in zip(target1, target2))
        elif is_vec2(target1) and is_vec2(target2):
            return abs(target1.x - target2.x) < EPSILON and abs(target1.y - target2.y) < EPSILON
        else:
            return target1 == target2

    @property
    def layers(self) -> list[str]:
        """Get list of active layer names"""
        return list(self._layer_groups.keys())

    def add_stop_callback(self, callback):
        """Add a callback to be executed when the frame loop stops"""
        self._stop_callbacks.append(callback)

    # ========================================================================
    # BEHAVIOR METHODS (100% shared)
    # ========================================================================

    def _apply_throttle_behavior(self, builder: 'BaseActiveBuilder', layer: str) -> bool:
        """Returns True if throttled (should skip), False if allowed to proceed"""
        throttle_key = self._get_throttle_key(layer, builder)
        has_time_arg = bool(builder.config.behavior_args)

        if has_time_arg:
            throttle_ms = builder.config.behavior_args[0]
            if throttle_key in self._throttle_times:
                elapsed = (time.perf_counter() - self._throttle_times[throttle_key]) * 1000
                if elapsed < throttle_ms:
                    return True
            self._throttle_times[throttle_key] = time.perf_counter()
            return False
        else:
            if layer in self._layer_groups:
                group = self._layer_groups[layer]
                active_throttled_count = sum(1 for b in group.builders if b.config.behavior == "throttle")
                if active_throttled_count > 0:
                    return True
            return False

    def _apply_debounce_behavior(self, builder: 'BaseActiveBuilder', layer: str):
        """Schedule builder for delayed execution"""
        if not builder.config.behavior_args:
            raise ConfigError("debounce() requires a delay in milliseconds")

        delay_ms = builder.config.behavior_args[0]
        debounce_key = self._get_debounce_key(layer, builder.config)

        if debounce_key in self._debounce_pending:
            _, _, _, old_cron_job = self._debounce_pending[debounce_key]
            if old_cron_job is not None:
                self._cancel_cron(old_cron_job)

        target_time = time.perf_counter() + (delay_ms / 1000.0)

        cron_job = None
        if self._frame_loop_job is None:
            def execute_debounced():
                if debounce_key in self._debounce_pending:
                    _, config, is_base, _ = self._debounce_pending[debounce_key]
                    del self._debounce_pending[debounce_key]
                    config.behavior = None
                    config.behavior_args = ()
                    actual_builder = self._create_active_builder(config, is_base)
                    self.add_builder(actual_builder)

            cron_job = self._schedule_cron_after(f"{delay_ms}ms", execute_debounced)

        self._debounce_pending[debounce_key] = (target_time, builder.config, builder.config.is_base_layer(), cron_job)

    def _check_and_update_rate_cache(self, builder: 'BaseActiveBuilder', layer: str) -> bool:
        """Returns True if builder should be skipped"""
        rate_cache_key = self._get_rate_cache_key(layer, builder.config)
        if rate_cache_key is None:
            return False

        if rate_cache_key in self._rate_builder_cache:
            cached_builder, cached_target = self._rate_builder_cache[rate_cache_key]
            targets_match = self._targets_match(builder.target_value, cached_target)

            if targets_match and layer in self._layer_groups:
                return True
            else:
                if layer in self._layer_groups:
                    group = self._layer_groups[layer]
                    old_current_value = group.get_current_value()
                    if is_vec2(old_current_value):
                        builder.base_value = Vec2(old_current_value.x, old_current_value.y)
                    else:
                        builder.base_value = old_current_value
                    builder.target_value = builder._calculate_target_value()

        self._rate_builder_cache[rate_cache_key] = (builder, builder.target_value)
        return False

    def _apply_replace_behavior(self, builder: 'BaseActiveBuilder', group: 'BaseLayerGroup'):
        """Apply replace behavior - snapshot current and reset"""
        current_value = group.get_current_value()
        group.clear_builders()

        if not group.is_base:
            # Reset accumulated to mode identity - builder.base_value captures the snapshot
            if group.mode == "scale":
                group.accumulated_value = identity_value_for_kind(group.property_kind)
            else:
                group.accumulated_value = zero_value_for_kind(group.property_kind)

        if is_vec2(current_value):
            builder.base_value = current_value
        elif isinstance(current_value, (int, float)):
            builder.base_value = current_value
        else:
            builder.base_value = current_value

        builder.target_value = builder._calculate_target_value()

    def _apply_stack_behavior(self, builder: 'BaseActiveBuilder', group: 'BaseLayerGroup') -> bool:
        """Returns True if at stack limit (should skip builder)"""
        if builder.config.behavior_args:
            max_count = builder.config.behavior_args[0]
            if max_count > 0:
                non_revert_builders = sum(
                    1 for b in group.builders
                    if not (b.lifecycle.phase == LifecyclePhase.REVERT or
                            (b.group_lifecycle and b.group_lifecycle.phase == LifecyclePhase.REVERT))
                )
                accumulated_slots = 0
                if not group.is_base and not group._is_reverted_to_zero():
                    accumulated_slots = 1
                if non_revert_builders + accumulated_slots >= max_count:
                    return True
                reverting_builders = [
                    b for b in group.builders
                    if (b.lifecycle.phase == LifecyclePhase.REVERT or
                        (b.group_lifecycle and b.group_lifecycle.phase == LifecyclePhase.REVERT))
                ]
                for b in reverting_builders:
                    group.remove_builder(b)
        return False

    def _apply_queue_behavior(self, builder: 'BaseActiveBuilder', group: 'BaseLayerGroup') -> bool:
        """Returns True if builder was enqueued (caller should return early)"""
        if builder.config.behavior_args:
            max_count = builder.config.behavior_args[0]
            total = len(group.builders) + len(group.pending_queue)
            if total >= max_count:
                return True

        if group.is_queue_active or len(group.pending_queue) > 0:
            def execute_callback():
                builder.creation_time = time.perf_counter()
                builder.lifecycle.started = False
                if group.is_base:
                    builder.base_value = builder._get_current_or_base_value()
                    builder.target_value = builder._calculate_target_value()
                if builder.config.max_value is not None:
                    group.max_value = builder.config.max_value
                if builder.config.min_value is not None:
                    group.min_value = builder.config.min_value
                group.add_builder(builder)
                if not builder.lifecycle.is_complete():
                    self._ensure_frame_loop_running()

            group.enqueue_builder(execute_callback)
            return True
        else:
            group.is_queue_active = True
            return False

    def _check_debounce_pending(self, current_time: float):
        """Check and execute any pending debounced builders"""
        keys_to_execute = []
        for key, (target_time, config, is_base, cron_job) in self._debounce_pending.items():
            if current_time >= target_time:
                keys_to_execute.append(key)

        for key in keys_to_execute:
            _, config, is_base, cron_job = self._debounce_pending[key]
            del self._debounce_pending[key]
            config.behavior = None
            config.behavior_args = ()
            actual_builder = self._create_active_builder(config, is_base)
            self.add_builder(actual_builder)

    # ========================================================================
    # TRIGGER REVERT (100% shared)
    # ========================================================================

    def trigger_revert(self, layer_name: str, revert_ms: Optional[float] = None, easing: str = "linear"):
        """Trigger revert on a layer"""
        if layer_name not in self._layer_groups:
            return

        group = self._layer_groups[layer_name]
        current_time = time.perf_counter()

        if group.builders:
            for builder in group.builders:
                builder.lifecycle.trigger_revert(current_time, revert_ms, easing)
        else:
            # No active builders, but group has accumulated_value.
            # Create a revert builder to transition accumulated_value to zero.
            if not group._is_reverted_to_zero():
                config = self._create_config()
                config.layer_name = layer_name
                config.property = group.property
                config.mode = group.mode
                config.operator = "to"

                if isinstance(group.accumulated_value, Vec2):
                    config.value = (group.accumulated_value.x, group.accumulated_value.y)
                else:
                    config.value = group.accumulated_value

                config.over_ms = 0
                config.revert_ms = revert_ms if revert_ms is not None else 0
                config.revert_easing = easing

                saved_accumulated = group.accumulated_value.copy() if isinstance(group.accumulated_value, Vec2) else group.accumulated_value

                if isinstance(group.accumulated_value, Vec2):
                    group.accumulated_value = Vec2(0, 0)
                else:
                    group.accumulated_value = 0.0

                active = self._create_active_builder(config, False)
                active.target_value = saved_accumulated

                active.lifecycle.start(current_time)
                active.lifecycle.phase = LifecyclePhase.REVERT
                active.lifecycle.phase_start_time = current_time

                group.add_builder(active)

        self._ensure_frame_loop_running()

    # ========================================================================
    # ADD BUILDER PIPELINE (100% shared)
    # ========================================================================

    def add_builder(self, builder: 'BaseActiveBuilder'):
        """Add a builder to its layer group - the main pipeline"""
        layer = builder.config.layer_name

        if builder.config.operator == "bake":
            self._bake_property(builder.config.property, layer if not builder.config.is_base_layer() else None)
            return

        if builder.config.behavior == "debounce":
            self._apply_debounce_behavior(builder, layer)
            return

        should_skip_cached = self._check_and_update_rate_cache(builder, layer)
        if should_skip_cached:
            return

        group = self._get_or_create_group(builder)

        if builder.config.max_value is not None:
            group.max_value = builder.config.max_value
        if builder.config.min_value is not None:
            group.min_value = builder.config.min_value

        behavior = builder.config.get_effective_behavior()

        if behavior == "throttle":
            is_throttled = self._apply_throttle_behavior(builder, layer)
            if is_throttled:
                return

        if behavior == "replace":
            self._apply_replace_behavior(builder, group)
        elif behavior == "stack":
            is_at_stack_limit = self._apply_stack_behavior(builder, group)
            if is_at_stack_limit:
                return
        elif behavior == "queue":
            was_enqueued = self._apply_queue_behavior(builder, group)
            if was_enqueued:
                return

        group.add_builder(builder)

        if not builder.lifecycle.is_complete():
            self._ensure_frame_loop_running()
        else:
            self._finalize_builder_completion(builder, group)

    def _finalize_builder_completion(self, builder: 'BaseActiveBuilder', group: 'BaseLayerGroup'):
        """Handle builder completion and cleanup"""
        layer = builder.config.layer_name

        bake_result = group.on_builder_complete(builder)
        if bake_result == "bake_to_base":
            self._bake_group_to_base(group)

        group.remove_builder(builder)

        if not group.should_persist():
            if layer in self._layer_groups:
                del self._layer_groups[layer]
            if layer in self._layer_orders:
                del self._layer_orders[layer]

    # ========================================================================
    # FRAME LOOP (100% shared structure)
    # ========================================================================

    def _ensure_frame_loop_running(self):
        """Start frame loop if not already running"""
        if self._frame_loop_job is None:
            self._last_frame_time = time.perf_counter()
            self._frame_loop_job = self._schedule_cron_interval(
                self._get_frame_interval_str(),
                self._tick_frame
            )

    def _stop_frame_loop(self):
        """Stop the frame loop"""
        if self._frame_loop_job is not None:
            self._cancel_cron(self._frame_loop_job)
            self._frame_loop_job = None
            self._last_frame_time = None

            # Execute stop callbacks
            callbacks = self._stop_callbacks.copy()
            self._stop_callbacks.clear()
            for cb in callbacks:
                try:
                    cb()
                except Exception as e:
                    print(f"Error in stop callback: {e}")

    def _stop_frame_loop_if_done(self):
        """Stop frame loop if no active builders remain"""
        if not self._should_frame_loop_be_active():
            self._stop_frame_loop()

    def _should_frame_loop_be_active(self) -> bool:
        """Check if frame loop should be running"""
        if self._layer_groups:
            return True
        if self._debounce_pending:
            return True
        return False

    def _calculate_delta_time(self) -> float:
        """Calculate delta time since last frame"""
        current_time = time.perf_counter()
        if self._last_frame_time is None:
            dt = 0.016  # Default ~60fps
        else:
            dt = current_time - self._last_frame_time
        self._last_frame_time = current_time
        return dt

    def _advance_all_builders(self, current_time: float):
        """Advance all builder lifecycles and handle completions"""
        groups_to_remove = []

        for layer_name, group in list(self._layer_groups.items()):
            phase_transitions, builders_to_remove = group.advance(current_time)

            # Execute phase callbacks
            for builder, completed_phase in phase_transitions:
                builder.lifecycle.execute_callbacks(completed_phase)

            # Handle completed builders
            for builder, bake_result in builders_to_remove:
                if bake_result == "bake_to_base":
                    self._bake_group_to_base(group)
                group.remove_builder(builder)

            # Track empty groups for removal
            if not group.should_persist():
                groups_to_remove.append(layer_name)

        # Remove empty groups
        for layer_name in groups_to_remove:
            if layer_name in self._layer_groups:
                del self._layer_groups[layer_name]
            if layer_name in self._layer_orders:
                del self._layer_orders[layer_name]

    # ========================================================================
    # CRON ABSTRACTION (overridable for testing)
    # ========================================================================

    def _cancel_cron(self, job):
        """Cancel a cron job. Override for testing."""
        from talon import cron
        cron.cancel(job)

    def _schedule_cron_after(self, delay: str, callback):
        """Schedule a one-shot cron job. Override for testing."""
        from talon import cron
        return cron.after(delay, callback)

    def _schedule_cron_interval(self, interval: str, callback):
        """Schedule a repeating cron job. Override for testing."""
        from talon import cron
        return cron.interval(interval, callback)

    def _get_frame_interval_str(self) -> str:
        """Get frame interval string for cron. Override to customize."""
        return "16ms"

    # ========================================================================
    # CONFIG FACTORY (overridable)
    # ========================================================================

    def _create_config(self) -> 'BaseBuilderConfig':
        """Create a new config instance. Override to return device-specific config."""
        return BaseBuilderConfig()

    # ========================================================================
    # BAKE / REMOVE / REVERSE (concrete, overridable)
    # ========================================================================

    def emit_layer(self, layer_name: str, ms: float = 1000, easing: str = "linear") -> Optional[str]:
        """Detach a layer: copy it anonymously, remove original, fade copy to zero.

        Creates a temporary "emit" copy of the layer that fades to neutral zero,
        then removes itself. The original layer is removed immediately (without baking).

        Returns:
            The emit layer name, or None if the layer was not found.
        """
        group = self._layer_groups.get(layer_name)
        if group is None:
            return None

        emit_name = f"emit.{layer_name}.{int(time.perf_counter() * 1000000)}"
        emit_group = group.copy(emit_name)
        emit_group.is_emit_layer = True

        # Fix builder group references: shallow copy shares builder objects
        # that still point to original group
        for builder in emit_group.builders:
            builder.group = emit_group

        # Remove original layer (without baking)
        self.remove_layer(layer_name, bake=False)

        # Register emit copy
        self._layer_groups[emit_name] = emit_group
        self._layer_orders[emit_name] = emit_group.order if emit_group.order is not None else self._next_auto_order

        # Fade to zero
        self.trigger_revert(emit_name, ms, easing)

        return emit_name

    def remove_layer(self, layer: str, bake: bool = False):
        """Remove a layer group, optionally baking base layers first.

        Cleans up rate_builder_cache and throttle_times for all builders in the group.
        """
        if layer not in self._layer_groups:
            return

        group = self._layer_groups[layer]

        if bake and group.is_base:
            self._bake_group_to_base(group)

        for builder in group.builders:
            rate_cache_key = self._get_rate_cache_key(layer, builder.config)
            if rate_cache_key is not None and rate_cache_key in self._rate_builder_cache:
                del self._rate_builder_cache[rate_cache_key]

            throttle_key = self._get_throttle_key(layer, builder)
            if throttle_key in self._throttle_times:
                del self._throttle_times[throttle_key]

        if layer in self._layer_groups:
            del self._layer_groups[layer]
        if layer in self._layer_orders:
            del self._layer_orders[layer]

    def reverse_all_directions(self):
        """Reverse direction/vector values for all non-emit layer groups.

        Negates accumulated_value and builder target_value/base_value for groups
        with DIRECTION or VECTOR property_kind. Skips emit layers.

        Device rigs should override to also flip their base state direction fields.
        """
        for layer_group in self._layer_groups.values():
            if layer_group.is_emit_layer:
                continue

            if layer_group.property_kind in (PropertyKind.DIRECTION, PropertyKind.VECTOR):
                if layer_group.accumulated_value is not None:
                    layer_group.accumulated_value = layer_group.accumulated_value * -1

                for builder in layer_group.builders:
                    if builder.target_value is not None:
                        builder.target_value = builder.target_value * -1
                    if builder.base_value is not None:
                        builder.base_value = builder.base_value * -1

    # ========================================================================
    # ABSTRACT METHODS (9 - device rigs implement)
    # ========================================================================

    @abstractmethod
    def bake_all(self):
        """Flatten all layers (base + user) into base state, then clear all layers.

        Device rigs must implement this because writing to base state fields
        (e.g., _base_speed, _base_left_stick) is device-specific.
        """
        ...

    @abstractmethod
    def _get_or_create_group(self, builder: 'BaseActiveBuilder') -> 'BaseLayerGroup':
        """Get existing group or create new one for this builder.

        Must:
        - Initialize accumulated_value from device base state for base layers
        - Initialize override mode layers with current computed value
        - Track order
        - Store group in self._layer_groups
        """
        ...

    @abstractmethod
    def _compute_current_state(self):
        """Compute current state by applying all active layers to base.

        Returns device-specific tuple (e.g., mouse returns position/speed/direction,
        gamepad returns sticks/triggers).
        """
        ...

    @abstractmethod
    def _apply_group(self, group: 'BaseLayerGroup', *accumulated):
        """Apply a single layer group's value to accumulated state.

        Takes and returns device-specific accumulated values.
        """
        ...

    @abstractmethod
    def _tick_frame(self):
        """Frame loop body - advance builders, compute output, emit to hardware."""
        ...

    @abstractmethod
    def _bake_group_to_base(self, group: 'BaseLayerGroup'):
        """Write a base layer group's current value into base state fields."""
        ...

    @abstractmethod
    def _bake_property(self, property_name: str, layer: Optional[str] = None):
        """Bake current computed value of a property into base state."""
        ...

    @abstractmethod
    def stop(self, transition_ms: Optional[float] = None, easing: str = "linear"):
        """Stop all activity, optionally with a smooth transition."""
        ...

    @abstractmethod
    def _create_active_builder(self, config: 'BaseBuilderConfig', is_base: bool) -> 'BaseActiveBuilder':
        """Factory for device-specific ActiveBuilder instances."""
        ...
