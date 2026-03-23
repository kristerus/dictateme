"""Core module: orchestrator, config, events, and shared types."""

from .config import AppConfig, load_config
from .event_bus import EventBus
from .events import Event, EventType
from .types import (
    ActiveWindowInfo,
    AppState,
    HotkeyMode,
    InsertionMethod,
    ProcessedText,
    ProcessingContext,
    TextFormat,
    TranscriptionResult,
    TranscriptionSegment,
)

__all__ = [
    "ActiveWindowInfo",
    "AppConfig",
    "AppState",
    "Event",
    "EventBus",
    "EventType",
    "HotkeyMode",
    "InsertionMethod",
    "ProcessedText",
    "ProcessingContext",
    "TextFormat",
    "TranscriptionResult",
    "TranscriptionSegment",
    "load_config",
]
