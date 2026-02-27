"""BaseLayerGroup - Container for builders on a single layer

Parameterized by PropertyKind instead of hardcoded property name checks.
Each layer gets a LayerGroup managing:
- Active builders (operations in progress)
- Accumulated state (for modifier layers)
- Queue system (sequential execution)
- Lifecycle (for group-level operations like revert)

Shared between all device rigs.
"""

import time
from typing import Optional, Any, Callable, TYPE_CHECKING
from collections import deque

from .vec2 import Vec2, is_vec2, EPSILON
from .property_kind import PropertyKind, zero_value_for_kind, identity_value_for_kind
from .lifecycle import Lifecycle

if TYPE_CHECKING:
    from .builder import BaseActiveBuilder


class BaseLayerGroup:
    """Container for all builders on a single layer

    Parameterized by PropertyKind for zero/identity values instead of
    hardcoded property name checks.
    """

    def __init__(
        self,
        layer_name: str,
        property: str,
        property_kind: PropertyKind,
        mode: Optional[str],
        layer_type: str,
        order: Optional[int] = None,
    ):
        from .contracts import LayerType

        self.layer_name = layer_name
        self.property = property
        self.property_kind = property_kind
        self.mode = mode
        self.layer_type = layer_type
        self.is_base = (layer_type == LayerType.BASE)
        self.order = order
        self.creation_time = time.perf_counter()
        self.builders: list['BaseActiveBuilder'] = []

        # Accumulated state (for modifier layers - persists after builders complete)
        if property_kind == PropertyKind.DIRECTION and mode == "offset":
            self.accumulated_value: Any = None
        elif mode == "scale":
            self.accumulated_value: Any = identity_value_for_kind(property_kind)
        else:
            self.accumulated_value: Any = zero_value_for_kind(property_kind)

        # Cached final target value
        self.final_target: Optional[Any] = None

        # Queue system (sequential execution within this layer)
        self.pending_queue: deque[Callable] = deque()
        self.is_queue_active: bool = False

        # Constraints (max/min clamping on layer output)
        self.max_value: Optional[float] = None
        self.min_value: Optional[float] = None

        # Emit/copy tracking
        self.is_emit_layer: bool = False
        self.source_layer: Optional[str] = None

        # Group-level lifecycle (for rig.layer("name").revert() operations)
        self.group_lifecycle: Optional[Lifecycle] = None

    def _zero_value(self) -> Any:
        """Get zero/identity value for this property kind"""
        return zero_value_for_kind(self.property_kind)

    def copy(self, new_name: str) -> 'BaseLayerGroup':
        """Create a copy of this layer group with a new name.

        Copies shared fields. Subclasses should override to copy device-specific fields.
        """
        copy_group = BaseLayerGroup(
            layer_name=new_name,
            property=self.property,
            property_kind=self.property_kind,
            mode=self.mode,
            layer_type=self.layer_type,
            order=self.order,
        )
        copy_group.source_layer = self.layer_name
        copy_group.builders = self.builders.copy()
        if is_vec2(self.accumulated_value):
            copy_group.accumulated_value = Vec2(self.accumulated_value.x, self.accumulated_value.y)
        else:
            copy_group.accumulated_value = self.accumulated_value
        copy_group.final_target = self.final_target
        copy_group.max_value = self.max_value
        copy_group.min_value = self.min_value
        return copy_group

    def _apply_constraints(self, value: Any) -> Any:
        """Apply max/min constraints to a value"""
        if self.max_value is None and self.min_value is None:
            return value

        if isinstance(value, (int, float)):
            if self.max_value is not None:
                value = min(value, self.max_value)
            if self.min_value is not None:
                value = max(value, self.min_value)
            return value

        if is_vec2(value):
            import math
            mag = math.sqrt(value.x * value.x + value.y * value.y)
            if mag < EPSILON:
                return value
            if self.max_value is not None and mag > self.max_value:
                scale = self.max_value / mag
                return Vec2(value.x * scale, value.y * scale)
            if self.min_value is not None and mag < self.min_value:
                scale = self.min_value / mag
                return Vec2(value.x * scale, value.y * scale)
            return value

        return value

    def add_builder(self, builder: 'BaseActiveBuilder'):
        """Add a builder to this group"""
        self.builders.append(builder)
        builder.group = self
        self._recalculate_final_target()

    def remove_builder(self, builder: 'BaseActiveBuilder'):
        """Remove a builder from this group"""
        if builder in self.builders:
            self.builders.remove(builder)
            self._recalculate_final_target()

    def clear_builders(self):
        """Remove all active builders (used by replace behavior)"""
        self.builders.clear()
        self._recalculate_final_target()

    def bake_builder(self, builder: 'BaseActiveBuilder') -> str:
        """Builder completed - bake its value

        Returns:
            "bake_to_base" for base layers (including reverted ones)
            "baked_to_group" for modifier layers
            "reverted" for modifier layers that reverted (clears accumulated value)
        """
        if builder.lifecycle.has_reverted():
            if self.is_base:
                return "bake_to_base"
            else:
                if self.mode == "scale":
                    self.accumulated_value = identity_value_for_kind(self.property_kind)
                elif is_vec2(self.accumulated_value):
                    self.accumulated_value = Vec2(0, 0)
                else:
                    self.accumulated_value = 0.0
                return "reverted"

        value = builder.get_interpolated_value()

        if self.is_base:
            return "bake_to_base"

        # Modifier layers: accumulate in group
        if self.accumulated_value is None:
            if self.mode == "scale":
                self.accumulated_value = identity_value_for_kind(self.property_kind)
            elif isinstance(value, (int, float)):
                self.accumulated_value = 0.0
            elif is_vec2(value):
                self.accumulated_value = Vec2(0, 0)
            else:
                self.accumulated_value = value

        self.accumulated_value = self._apply_mode(self.accumulated_value, value, builder.config.mode)
        self.accumulated_value = self._apply_constraints(self.accumulated_value)

        return "baked_to_group"

    def _apply_mode(self, current: Any, incoming: Any, mode: Optional[str]) -> Any:
        """Apply mode operation to combine values within this layer group"""
        if mode == "offset" or mode == "add":
            if current is None:
                return incoming
            if isinstance(current, (int, float)) and isinstance(incoming, (int, float)):
                return current + incoming
            if is_vec2(current) and is_vec2(incoming):
                return Vec2(current.x + incoming.x, current.y + incoming.y)
            if isinstance(current, (int, float)) and is_vec2(incoming):
                return incoming
            if is_vec2(current) and isinstance(incoming, (int, float)):
                return current
            return incoming
        elif mode == "override":
            return incoming
        elif mode == "scale" or mode == "mul":
            if is_vec2(current) and isinstance(incoming, (int, float)):
                return Vec2(current.x * incoming, current.y * incoming)
            if isinstance(current, (int, float)) and isinstance(incoming, (int, float)):
                return current * incoming
            return incoming
        else:
            if is_vec2(current) and is_vec2(incoming):
                return Vec2(current.x + incoming.x, current.y + incoming.y)
            if isinstance(current, (int, float)) and isinstance(incoming, (int, float)):
                return current + incoming
            return incoming

    def get_current_value(self) -> Any:
        """Get aggregated value: accumulated + all active builders"""
        if self.is_base:
            if not self.builders:
                return self._apply_constraints(self.accumulated_value)
            last_value = self.accumulated_value
            for builder in self.builders:
                builder_value = builder.get_interpolated_value()
                if builder_value is not None:
                    last_value = builder_value
            return self._apply_constraints(last_value)

        result = self.accumulated_value

        if result is None:
            if self.mode == "scale":
                result = identity_value_for_kind(self.property_kind)
            elif self.builders:
                first_value = self.builders[0].get_interpolated_value()
                if is_vec2(first_value):
                    result = Vec2(0, 0)
                else:
                    result = 0.0
            else:
                result = 0.0

        for builder in self.builders:
            builder_value = builder.get_interpolated_value()
            if builder_value is not None:
                result = self._apply_mode(result, builder_value, builder.config.mode)

        return self._apply_constraints(result)

    def _recalculate_final_target(self):
        """Recalculate cached final target value after all builders complete"""
        if not self.builders:
            self.final_target = None
            return

        if self.is_base:
            self.final_target = self.builders[-1].target_value
            return

        result = self.accumulated_value

        if result is None:
            if self.mode == "scale":
                result = identity_value_for_kind(self.property_kind)
            else:
                first_target = self.builders[0].target_value
                if is_vec2(first_target):
                    result = Vec2(0, 0)
                else:
                    result = 0.0

        for builder in self.builders:
            target = builder.target_value
            if target is not None:
                result = self._apply_mode(result, target, builder.config.mode)

        self.final_target = result

    @property
    def value(self) -> Any:
        """Current value (accumulated + all active builders)"""
        return self.get_current_value()

    @property
    def target(self) -> Optional[Any]:
        """Final target value after all active builders complete (cached)"""
        return self.final_target

    def should_persist(self) -> bool:
        """Should this group stay alive?"""
        if len(self.builders) > 0:
            return True
        if self.is_base:
            return False
        is_zero = self._is_reverted_to_zero()
        return not is_zero

    def _is_reverted_to_zero(self) -> bool:
        """Check if accumulated value is effectively at neutral (zero for offset, identity for scale)"""
        if self.accumulated_value is None:
            return True
        if self.mode == "scale":
            # Scale identity is 1.0 / Vec2(1, 1)
            if is_vec2(self.accumulated_value):
                return (abs(self.accumulated_value.x - 1.0) < EPSILON and
                        abs(self.accumulated_value.y - 1.0) < EPSILON)
            if isinstance(self.accumulated_value, (int, float)):
                return abs(self.accumulated_value - 1.0) < EPSILON
            return False
        if is_vec2(self.accumulated_value):
            return (abs(self.accumulated_value.x) < EPSILON and
                    abs(self.accumulated_value.y) < EPSILON)
        if isinstance(self.accumulated_value, (int, float)):
            return abs(self.accumulated_value) < EPSILON
        return False

    def enqueue_builder(self, execution_callback: Callable):
        """Add a builder to this group's queue"""
        self.pending_queue.append(execution_callback)

    def start_next_queued(self) -> bool:
        """Start next queued builder if available"""
        if len(self.pending_queue) == 0:
            self.is_queue_active = False
            return False
        callback = self.pending_queue.popleft()
        self.is_queue_active = True
        callback()
        return True

    def on_builder_complete(self, builder: 'BaseActiveBuilder'):
        """Called when a builder completes - handle queue progression"""
        bake_result = self.bake_builder(builder)

        if len(self.pending_queue) > 0:
            self.start_next_queued()

        return bake_result

    def advance(self, current_time: float) -> list[tuple['BaseActiveBuilder', str]]:
        """Advance all builders in this group

        Returns:
            Tuple of (phase_transitions, builders_to_remove)
        """
        phase_transitions = []
        builders_to_remove = []

        for builder in self.builders:
            old_phase = builder.lifecycle.phase
            builder.advance(current_time)
            new_phase = builder.lifecycle.phase

            if old_phase != new_phase and old_phase is not None:
                phase_transitions.append((builder, old_phase))

            is_complete = builder.lifecycle.is_complete()
            should_gc = builder.lifecycle.should_be_garbage_collected()

            if old_phase is not None and new_phase is None:
                builder._marked_for_removal = True
                bake_result = self.on_builder_complete(builder)
                builders_to_remove.append((builder, bake_result))
            elif should_gc:
                builder._marked_for_removal = True
                bake_result = self.on_builder_complete(builder)
                builders_to_remove.append((builder, bake_result))

        return phase_transitions, builders_to_remove

    def __repr__(self) -> str:
        return f"<BaseLayerGroup '{self.layer_name}' {self.property} kind={self.property_kind.value} mode={self.mode} builders={len(self.builders)} accumulated={self.accumulated_value}>"
