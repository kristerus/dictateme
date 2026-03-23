"""Clipboard operations: save, restore, copy, and paste via Win32."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def get_clipboard_text() -> str | None:
    """Read current clipboard text content.

    Returns:
        Clipboard text or None if clipboard is empty or not text.
    """
    import win32clipboard

    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                return data
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        logger.warning("Failed to read clipboard")
    return None


def set_clipboard_text(text: str) -> bool:
    """Set clipboard to the given text.

    Returns:
        True if successful.
    """
    import win32clipboard

    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:
        logger.exception("Failed to set clipboard")
        return False


def clipboard_paste(text: str, restore: bool = True, restore_delay_ms: int = 100) -> bool:
    """Insert text via clipboard + Ctrl+V.

    This is the primary text insertion method. It:
    1. Saves current clipboard contents
    2. Sets clipboard to the target text
    3. Simulates Ctrl+V
    4. Restores original clipboard after a delay

    Args:
        text: Text to insert.
        restore: Whether to restore the original clipboard.
        restore_delay_ms: Delay before restoring clipboard (ms).

    Returns:
        True if the paste was sent successfully.
    """
    import keyboard

    # Save current clipboard
    original = None
    if restore:
        original = get_clipboard_text()

    # Set new text
    if not set_clipboard_text(text):
        return False

    # Small delay for clipboard to settle
    time.sleep(0.02)

    # Simulate Ctrl+V
    keyboard.send("ctrl+v")

    # Restore clipboard after delay
    if restore and original is not None:
        time.sleep(restore_delay_ms / 1000.0)
        set_clipboard_text(original)

    return True
