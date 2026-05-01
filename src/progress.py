"""Progress event emitter for the GPU Warm-Up Tool.

Provides thread-safe event distribution to multiple subscribers using queue.Queue.
Buffers all emitted events so late subscribers receive a full replay.
"""

import queue
import threading
from typing import List

from .models import ProgressEvent


class ProgressEmitter:
    """Publishes progress events to subscribers via thread-safe queues.

    Subscribers receive events through individual queue.Queue instances,
    enabling both SSE (web) and console consumers to receive updates independently.

    All emitted events are buffered so that new subscribers immediately receive
    a replay of past events, preventing data loss from late connections.
    """

    def __init__(self) -> None:
        """Initialize with empty subscriber list and event buffer."""
        self._subscribers: List[queue.Queue] = []
        self._buffer: List[ProgressEvent] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        """Return a new queue that will receive progress events.

        The queue is pre-populated with all previously emitted events so
        late subscribers don't miss anything.

        Returns:
            A queue.Queue instance that will receive all ProgressEvent objects.
        """
        q: queue.Queue = queue.Queue()
        with self._lock:
            # Replay buffered events so the subscriber catches up
            for event in self._buffer:
                q.put_nowait(event)
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        """Remove a subscriber so it no longer receives events.

        Args:
            q: The queue previously returned by subscribe().
        """
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass  # Already removed or never subscribed

    def emit(self, event: ProgressEvent) -> None:
        """Publish a progress event to all subscribers and print to console.

        The event is also appended to the internal buffer for late subscribers.

        Args:
            event: The ProgressEvent to distribute.
        """
        print(f"[{event.event_type.value}] {event.message}")
        with self._lock:
            self._buffer.append(event)
            for q in self._subscribers:
                q.put_nowait(event)
