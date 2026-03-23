"""Win32 SendInput wrapper for character-by-character text insertion."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import time

logger = logging.getLogger(__name__)

# Win32 constants
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("_input", _INPUT_UNION),
    ]


def send_unicode_string(text: str, char_delay_ms: float = 5) -> bool:
    """Send a string character by character using Win32 SendInput.

    Each character is sent as a Unicode keypress event. This method
    works with applications that don't accept clipboard paste but
    is slower for long text.

    Args:
        text: Text to type.
        char_delay_ms: Delay between characters in milliseconds.

    Returns:
        True if all characters were sent.
    """
    try:
        for char in text:
            _send_unicode_char(char)
            if char_delay_ms > 0:
                time.sleep(char_delay_ms / 1000.0)
        return True
    except Exception:
        logger.exception("SendInput failed")
        return False


def _send_unicode_char(char: str) -> None:
    """Send a single Unicode character via SendInput (key down + key up)."""
    code = ord(char)

    # Key down
    inputs = (INPUT * 2)()
    inputs[0].type = INPUT_KEYBOARD
    inputs[0].ki.wVk = 0
    inputs[0].ki.wScan = code
    inputs[0].ki.dwFlags = KEYEVENTF_UNICODE
    inputs[0].ki.time = 0
    inputs[0].ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

    # Key up
    inputs[1].type = INPUT_KEYBOARD
    inputs[1].ki.wVk = 0
    inputs[1].ki.wScan = code
    inputs[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
    inputs[1].ki.time = 0
    inputs[1].ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

    sent = ctypes.windll.user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    if sent != 2:
        raise OSError(f"SendInput returned {sent}, expected 2")
