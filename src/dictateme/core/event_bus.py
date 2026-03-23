"""Simple publish/subscribe event dispatcher.

All inter-component communication flows through the EventBus.
Components subscribe to specific event types and receive callbacks
when those events are emitted.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .events import Event, EventType

logger = logging.getLogger(__name__)

Listener = Callable[["Event"], None]


class EventBus:
    """Thread-safe publish/subscribe event dispatcher.

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.HOTKEY_PRESSED, my_handler)
        bus.emit(Event(type=EventType.HOTKEY_PRESSED, data={"key": "ctrl+win"}))
    """

    def __init__(self) -> None:
        self._listeners: dict[EventType, list[Listener]] = defaultdict(list)

    def subscribe(self, event_type: EventType, listener: Listener) -> None:
        """Register a listener for a specific event type."""
        self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: EventType, listener: Listener) -> None:
        """Remove a previously registered listener."""
        try:
            self._listeners[event_type].remove(listener)
        except ValueError:
            pass

    def emit(self, event: Event) -> None:
        """Dispatch an event to all registered listeners.

        Sets the event timestamp and calls each listener synchronously.
        Exceptions in listeners are logged but do not prevent other
        listeners from being called.
        """
        event.timestamp = time.time()
        listeners = self._listeners.get(event.type, [])
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                logger.exception(
                    "Error in event listener for %s", event.type.name
                )

    def clear(self) -> None:
        """Remove all listeners."""
        self._listeners.clear()
