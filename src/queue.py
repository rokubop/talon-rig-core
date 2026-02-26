"""Queue system for behavior modes

Handles queuing of builders when behavior is set to 'queue'.
Each layer has its own queue with accumulated state tracking.

100% shared between all device rigs.
"""

from typing import Optional, Callable, Any
from collections import deque


class BuilderQueue:
    """Queue for a specific layer

    Manages sequential execution of builders on the same layer/property.
    """

    def __init__(self):
        self.queue: deque = deque()
        self.current: Optional[Callable] = None
        self.accumulated_state: dict[str, Any] = {}

    def enqueue(self, execution_callback: Callable) -> None:
        """Add a builder execution callback to the queue"""
        self.queue.append(execution_callback)

    def start_next(self) -> bool:
        """Start the next queued builder if available.

        Returns:
            True if a builder was started, False if queue is empty
        """
        if len(self.queue) == 0:
            self.current = None
            return False

        self.current = self.queue.popleft()
        self.current()
        return True

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def clear(self) -> None:
        """Clear all pending queue items and reset current"""
        self.queue.clear()
        self.current = None


class QueueManager:
    """Manages all builder queues across all layers"""

    def __init__(self):
        self.queues: dict[str, BuilderQueue] = {}

    def get_queue(self, layer: str) -> BuilderQueue:
        if layer not in self.queues:
            self.queues[layer] = BuilderQueue()
        return self.queues[layer]

    def enqueue(self, layer: str, execution_callback: Callable) -> None:
        """Add a builder to the specified queue"""
        queue = self.get_queue(layer)
        queue.enqueue(execution_callback)

    def on_builder_complete(self, layer: str, property: str, final_value):
        """Handle builder completion and start next queued item"""
        if layer in self.queues:
            queue = self.queues[layer]
            queue.accumulated_state[property] = final_value

            if not queue.start_next():
                del self.queues[layer]

    def clear_queue(self, layer: str) -> None:
        """Clear and remove the queue for a specific layer"""
        if layer in self.queues:
            self.queues[layer].clear()
            del self.queues[layer]

    def clear_all(self) -> None:
        """Clear all queues"""
        for queue in self.queues.values():
            queue.clear()
        self.queues.clear()

    def is_active(self, layer: str) -> bool:
        """Check if a queue exists and has items"""
        return layer in self.queues and not self.queues[layer].is_empty()
