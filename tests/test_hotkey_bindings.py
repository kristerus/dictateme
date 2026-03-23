"""Tests for hotkey binding utilities."""

from dictateme.hotkey.bindings import normalize_key_combo, parse_format_key


def test_normalize_common_aliases() -> None:
    assert normalize_key_combo("ctrl+win") == "ctrl+windows"
    assert normalize_key_combo("Ctrl+Windows") == "ctrl+windows"
    assert normalize_key_combo("ctrl+super") == "ctrl+windows"
    assert normalize_key_combo("control+meta") == "ctrl+windows"


def test_normalize_preserves_non_modifier_keys() -> None:
    assert normalize_key_combo("ctrl+shift+a") == "ctrl+shift+a"
    assert normalize_key_combo("alt+f1") == "alt+f1"


def test_parse_format_key_valid() -> None:
    assert parse_format_key("1") == 0
    assert parse_format_key("5") == 4
    assert parse_format_key("9") == 8


def test_parse_format_key_invalid() -> None:
    assert parse_format_key("0") is None
    assert parse_format_key("10") is None
    assert parse_format_key("a") is None
    assert parse_format_key("") is None
