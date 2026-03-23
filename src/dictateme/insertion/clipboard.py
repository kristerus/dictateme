"""Cross-platform clipboard operations: save, restore, copy, and paste.

Backends:
  - Windows: win32clipboard + keyboard
  - macOS:   pbcopy/pbpaste + pyobjc CGEvent
  - Linux:   xclip/xsel + xdotool (X11), wl-copy/wl-paste (Wayland)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time

logger = logging.getLogger(__name__)


# ── Clipboard read/write ────────────────────────────────────────

def get_clipboard_text() -> str | None:
    """Read current clipboard text content (cross-platform)."""
    if sys.platform == "win32":
        return _win_get_clipboard()
    elif sys.platform == "darwin":
        return _mac_get_clipboard()
    else:
        return _linux_get_clipboard()


def set_clipboard_text(text: str) -> bool:
    """Set clipboard to the given text (cross-platform)."""
    if sys.platform == "win32":
        return _win_set_clipboard(text)
    elif sys.platform == "darwin":
        return _mac_set_clipboard(text)
    else:
        return _linux_set_clipboard(text)


# ── Paste simulation ────────────────────────────────────────────

def simulate_paste() -> None:
    """Simulate the platform paste shortcut (Ctrl+V / Cmd+V)."""
    if sys.platform == "win32":
        _win_simulate_paste()
    elif sys.platform == "darwin":
        _mac_simulate_paste()
    else:
        _linux_simulate_paste()


def clipboard_paste(text: str, restore: bool = True, restore_delay_ms: int = 100) -> bool:
    """Insert text via clipboard + paste shortcut.

    1. Saves current clipboard
    2. Sets clipboard to target text
    3. Simulates paste
    4. Restores original clipboard after delay

    Args:
        text: Text to insert.
        restore: Whether to restore the original clipboard.
        restore_delay_ms: Delay before restoring clipboard (ms).

    Returns:
        True if the paste was sent successfully.
    """
    original = None
    if restore:
        original = get_clipboard_text()

    if not set_clipboard_text(text):
        return False

    time.sleep(0.02)
    simulate_paste()

    if restore and original is not None:
        time.sleep(restore_delay_ms / 1000.0)
        set_clipboard_text(original)

    return True


# ── Windows backend ─────────────────────────────────────────────

def _win_get_clipboard() -> str | None:
    import win32clipboard
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        logger.warning("Failed to read clipboard")
    return None


def _win_set_clipboard(text: str) -> bool:
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


def _win_simulate_paste() -> None:
    import keyboard
    keyboard.send("ctrl+v")


# ── macOS backend ───────────────────────────────────────────────

def _mac_get_clipboard() -> str | None:
    try:
        result = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=5
        )
        return result.stdout if result.returncode == 0 else None
    except Exception:
        logger.warning("Failed to read clipboard via pbpaste")
        return None


def _mac_set_clipboard(text: str) -> bool:
    try:
        subprocess.run(
            ["pbcopy"], input=text, text=True, timeout=5, check=True
        )
        return True
    except Exception:
        logger.exception("Failed to set clipboard via pbcopy")
        return False


def _mac_simulate_paste() -> None:
    """Simulate Cmd+V on macOS using osascript."""
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'],
            timeout=5,
            check=True,
        )
    except Exception:
        logger.exception("Failed to simulate paste on macOS")


# ── Linux backend ───────────────────────────────────────────────

def _linux_clipboard_tool() -> str | None:
    """Detect the best clipboard tool available."""
    if shutil.which("xclip"):
        return "xclip"
    if shutil.which("xsel"):
        return "xsel"
    if shutil.which("wl-copy"):
        return "wl"  # Wayland
    return None


def _linux_get_clipboard() -> str | None:
    tool = _linux_clipboard_tool()
    try:
        if tool == "xclip":
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5,
            )
        elif tool == "xsel":
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True, text=True, timeout=5,
            )
        elif tool == "wl":
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True, text=True, timeout=5,
            )
        else:
            logger.warning("No clipboard tool found (install xclip, xsel, or wl-clipboard)")
            return None
        return result.stdout if result.returncode == 0 else None
    except Exception:
        logger.warning("Failed to read clipboard on Linux")
        return None


def _linux_set_clipboard(text: str) -> bool:
    tool = _linux_clipboard_tool()
    try:
        if tool == "xclip":
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text, text=True, timeout=5, check=True,
            )
        elif tool == "xsel":
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text, text=True, timeout=5, check=True,
            )
        elif tool == "wl":
            subprocess.run(
                ["wl-copy"], input=text, text=True, timeout=5, check=True,
            )
        else:
            logger.warning("No clipboard tool found")
            return False
        return True
    except Exception:
        logger.exception("Failed to set clipboard on Linux")
        return False


def _linux_simulate_paste() -> None:
    """Simulate Ctrl+V on Linux using xdotool or ydotool."""
    try:
        if shutil.which("xdotool"):
            subprocess.run(["xdotool", "key", "ctrl+v"], timeout=5, check=True)
        elif shutil.which("ydotool"):
            subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], timeout=5, check=True)
        else:
            logger.warning("No key simulation tool found (install xdotool or ydotool)")
    except Exception:
        logger.exception("Failed to simulate paste on Linux")
