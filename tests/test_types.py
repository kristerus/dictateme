"""Tests for shared type definitions."""

from dictateme.core.types import (
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


def test_app_state_values() -> None:
    """AppState enum has all required states."""
    states = {s.value for s in AppState}
    assert states == {
        "idle", "recording", "transcribing",
        "llm_processing", "format_selection", "inserting",
    }


def test_text_format_values() -> None:
    """TextFormat enum has all format presets."""
    assert TextFormat.AS_IS.value == "as_is"
    assert TextFormat.FORMAL.value == "formal"
    assert TextFormat.CODE_COMMENT.value == "code_comment"


def test_transcription_result() -> None:
    """TranscriptionResult holds text and segments."""
    seg = TranscriptionSegment(start=0.0, end=1.5, text="hello", confidence=0.95)
    result = TranscriptionResult(
        text="hello",
        language="en",
        confidence=0.98,
        duration_seconds=1.5,
        segments=[seg],
    )
    assert result.text == "hello"
    assert len(result.segments) == 1
    assert result.segments[0].confidence == 0.95


def test_processing_context() -> None:
    """ProcessingContext captures app info."""
    ctx = ProcessingContext(app_name="Code", window_title="test.py - VS Code")
    assert ctx.app_name == "Code"
    assert ctx.field_hint is None


def test_active_window_info() -> None:
    """ActiveWindowInfo stores window metadata."""
    info = ActiveWindowInfo(
        hwnd=12345, title="Untitled", process_name="notepad.exe",
        process_id=999, is_elevated=False,
    )
    assert info.process_name == "notepad.exe"
    assert not info.is_elevated
