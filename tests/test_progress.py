"""Tests for Progress Emitter."""

import queue

from src.models import ProgressEvent, ProgressEventType
from src.progress import ProgressEmitter


class TestProgressEmitter:
    """Tests for ProgressEmitter."""

    def test_subscriber_receives_events(self):
        """Verify a subscriber receives emitted events."""
        emitter = ProgressEmitter()
        q = emitter.subscribe()

        event = ProgressEvent(
            event_type=ProgressEventType.WARMUP_STARTED,
            message="Starting",
        )
        emitter.emit(event)

        received = q.get_nowait()
        assert received.event_type == ProgressEventType.WARMUP_STARTED
        assert received.message == "Starting"

    def test_multiple_subscribers(self):
        """Verify all subscribers receive the same events."""
        emitter = ProgressEmitter()
        q1 = emitter.subscribe()
        q2 = emitter.subscribe()

        event = ProgressEvent(
            event_type=ProgressEventType.SESSION_COMPLETED,
            message="Done",
        )
        emitter.emit(event)

        assert q1.get_nowait().message == "Done"
        assert q2.get_nowait().message == "Done"

    def test_late_subscriber_gets_replay(self):
        """Verify late subscribers receive buffered events."""
        emitter = ProgressEmitter()

        event1 = ProgressEvent(
            event_type=ProgressEventType.WARMUP_STARTED,
            message="First",
        )
        emitter.emit(event1)

        # Subscribe after event was emitted
        q = emitter.subscribe()

        # Should have the buffered event
        received = q.get_nowait()
        assert received.message == "First"

    def test_unsubscribe(self):
        """Verify unsubscribed queues stop receiving events."""
        emitter = ProgressEmitter()
        q = emitter.subscribe()
        emitter.unsubscribe(q)

        event = ProgressEvent(
            event_type=ProgressEventType.WARMUP_COMPLETED,
            message="Done",
        )
        emitter.emit(event)

        assert q.empty()

    def test_event_order_preserved(self):
        """Verify events are received in order."""
        emitter = ProgressEmitter()
        q = emitter.subscribe()

        for i in range(5):
            emitter.emit(ProgressEvent(
                event_type=ProgressEventType.SESSION_COMPLETED,
                message=f"Event {i}",
            ))

        for i in range(5):
            assert q.get_nowait().message == f"Event {i}"
