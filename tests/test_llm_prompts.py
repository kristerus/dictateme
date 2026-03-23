"""Tests for LLM prompt building."""

from dictateme.core.types import ProcessingContext, TextFormat
from dictateme.llm.prompts import (
    build_cleanup_prompt,
    build_reformat_prompt,
)


def test_cleanup_prompt_includes_context() -> None:
    """Cleanup prompt interpolates app context."""
    ctx = ProcessingContext(app_name="chrome.exe", window_title="Gmail - Google Chrome")
    prompt = build_cleanup_prompt(ctx)

    assert "chrome.exe" in prompt
    assert "Gmail" in prompt
    assert "filler words" in prompt.lower()


def test_reformat_prompt_uses_format_name() -> None:
    """Reformat prompt includes the target format."""
    prompt = build_reformat_prompt(TextFormat.EMAIL)
    assert "email" in prompt.lower()


def test_reformat_prompt_custom_instruction() -> None:
    """Custom instruction overrides default format instructions."""
    prompt = build_reformat_prompt(
        TextFormat.CUSTOM,
        custom_instruction="Write as a haiku.",
    )
    assert "haiku" in prompt.lower()


def test_reformat_prompt_uses_presets() -> None:
    """Format presets from config are used when available."""
    presets = {"formal": "Make it super formal and British."}
    prompt = build_reformat_prompt(TextFormat.FORMAL, format_presets=presets)
    assert "British" in prompt
