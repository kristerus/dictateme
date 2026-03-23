"""Shared type definitions used across DictateMe modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AppState(Enum):
    """States of the core orchestrator state machine."""

    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    LLM_PROCESSING = "llm_processing"
    FORMAT_SELECTION = "format_selection"
    INSERTING = "inserting"


class TextFormat(Enum):
    """Available text formatting presets."""

    AS_IS = "as_is"
    FORMAL = "formal"
    CASUAL = "casual"
    EMAIL = "email"
    BULLET_POINTS = "bullet_points"
    CODE_COMMENT = "code_comment"
    AI_PROMPT = "ai_prompt"
    SLACK_MESSAGE = "slack_message"
    CUSTOM = "custom"


class InsertionMethod(Enum):
    """Methods for inserting text into the active application."""

    CLIPBOARD_PASTE = "clipboard_paste"
    SEND_INPUT_UNICODE = "sendinput_unicode"
    UI_AUTOMATION = "ui_automation"


class HotkeyMode(Enum):
    """Hotkey activation modes."""

    HOLD = "hold"
    TOGGLE = "toggle"


@dataclass
class ActiveWindowInfo:
    """Snapshot of the currently focused window."""

    hwnd: int
    title: str
    process_name: str
    process_id: int
    is_elevated: bool


@dataclass
class TranscriptionSegment:
    """A segment of transcribed audio with timing info."""

    start: float  # seconds
    end: float  # seconds
    text: str
    confidence: float


@dataclass
class TranscriptionResult:
    """Complete transcription output from the STT engine."""

    text: str
    language: str
    confidence: float
    duration_seconds: float
    segments: list[TranscriptionSegment]


@dataclass
class ProcessingContext:
    """Context about the active application for LLM processing."""

    app_name: str
    window_title: str
    field_hint: str | None = None


@dataclass
class ProcessedText:
    """Result of LLM text processing."""

    text: str
    format_applied: TextFormat
    model_used: str
    latency_ms: float
