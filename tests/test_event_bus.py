"""Tests for the event bus."""

from dictateme.core.event_bus import EventBus
from dictateme.core.events import Event, EventType


def test_subscribe_and_emit(event_bus: EventBus) -> None:
    """Listeners receive emitted events."""
    received: list[Event] = []
    event_bus.subscribe(EventType.HOTKEY_PRESSED, received.append)

    event = Event(type=EventType.HOTKEY_PRESSED)
    event_bus.emit(event)

    assert len(received) == 1
    assert received[0].type == EventType.HOTKEY_PRESSED
    assert received[0].timestamp > 0


def test_emit_only_to_matching_listeners(event_bus: EventBus) -> None:
    """Events only go to listeners subscribed to that type."""
    hotkey_events: list[Event] = []
    audio_events: list[Event] = []

    event_bus.subscribe(EventType.HOTKEY_PRESSED, hotkey_events.append)
    event_bus.subscribe(EventType.RECORDING_STARTED, audio_events.append)

    event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))

    assert len(hotkey_events) == 1
    assert len(audio_events) == 0


def test_unsubscribe(event_bus: EventBus) -> None:
    """Unsubscribed listeners no longer receive events."""
    received: list[Event] = []
    event_bus.subscribe(EventType.HOTKEY_PRESSED, received.append)
    event_bus.unsubscribe(EventType.HOTKEY_PRESSED, received.append)

    event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))

    assert len(received) == 0


def test_listener_exception_does_not_propagate(event_bus: EventBus) -> None:
    """A failing listener doesn't prevent other listeners from running."""
    received: list[Event] = []

    def bad_listener(event: Event) -> None:
        raise RuntimeError("boom")

    event_bus.subscribe(EventType.HOTKEY_PRESSED, bad_listener)
    event_bus.subscribe(EventType.HOTKEY_PRESSED, received.append)

    event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))

    assert len(received) == 1


def test_event_data_passthrough(event_bus: EventBus) -> None:
    """Event data dict is passed through to listeners."""
    received: list[Event] = []
    event_bus.subscribe(EventType.TRANSCRIPTION_COMPLETE, received.append)

    event_bus.emit(Event(
        type=EventType.TRANSCRIPTION_COMPLETE,
        data={"text": "hello world"},
    ))

    assert received[0].data["text"] == "hello world"


def test_clear(event_bus: EventBus) -> None:
    """Clear removes all listeners."""
    received: list[Event] = []
    event_bus.subscribe(EventType.HOTKEY_PRESSED, received.append)
    event_bus.clear()

    event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))

    assert len(received) == 0
