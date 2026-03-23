"""Event types for inter-component communication."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class EventType(Enum):
    """All event types in the DictateMe system."""

    # Hotkey events
    HOTKEY_PRESSED = auto()
    HOTKEY_RELEASED = auto()
    FORMAT_KEY_PRESSED = auto()
    CANCEL_PRESSED = auto()

    # Audio events
    RECORDING_STARTED = auto()
    RECORDING_STOPPED = auto()
    AUDIO_READY = auto()
    VAD_SPEECH_START = auto()
    VAD_SPEECH_END = auto()

    # STT events
    TRANSCRIPTION_STARTED = auto()
    TRANSCRIPTION_COMPLETE = auto()
    TRANSCRIPTION_PARTIAL = auto()

    # LLM events
    LLM_PROCESSING_STARTED = auto()
    LLM_PROCESSING_COMPLETE = auto()
    LLM_PROCESSING_SKIPPED = auto()

    # Insertion events
    TEXT_INSERTING = auto()
    TEXT_INSERTED = auto()
    TEXT_INSERTION_FAILED = auto()

    # System events
    ERROR = auto()
    STATE_CHANGED = auto()


@dataclass
class Event:
    """An event dispatched through the event bus.

    Attributes:
        type: The event type identifier.
        data: Arbitrary payload for the event.
        timestamp: Set by the event bus on dispatch.
    """

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
