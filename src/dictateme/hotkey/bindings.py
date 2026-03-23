"""Key combo definitions and parsing."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def normalize_key_combo(combo: str) -> str:
    """Normalize a key combo string for the keyboard library.

    Maps common aliases to the format keyboard expects.
    e.g., "ctrl+windows" -> "ctrl+windows", "ctrl+win" -> "ctrl+windows"

    Args:
        combo: Key combo string from config.

    Returns:
        Normalized key combo string.
    """
    # Normalize common aliases
    parts = [p.strip().lower() for p in combo.split("+")]
    normalized = []
    for part in parts:
        if part in ("win", "windows", "super", "meta"):
            normalized.append("windows")
        elif part in ("ctrl", "control"):
            normalized.append("ctrl")
        elif part in ("alt", "option"):
            normalized.append("alt")
        elif part in ("shift",):
            normalized.append("shift")
        else:
            normalized.append(part)
    return "+".join(normalized)


def parse_format_key(key_name: str) -> int | None:
    """Parse a format selection key press to a preset index.

    Keys 1-9 map to format presets. Returns None if not a format key.

    Args:
        key_name: The key name from keyboard event.

    Returns:
        0-based preset index, or None.
    """
    try:
        num = int(key_name)
        if 1 <= num <= 9:
            return num - 1
    except (ValueError, TypeError):
        pass
    return None
