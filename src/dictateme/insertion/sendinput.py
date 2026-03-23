"""Cross-platform character-by-character text input.

Backends:
  - Windows: Win32 SendInput (Unicode keypresses)
  - macOS:   osascript keystroke
  - Linux:   xdotool type
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time

logger = logging.getLogger(__name__)


def send_unicode_string(text: str, char_delay_ms: float = 5) -> bool:
    """Send a string character by character (cross-platform).

    Args:
        text: Text to type.
        char_delay_ms: Delay between characters in milliseconds.

    Returns:
        True if all characters were sent.
    """
    if sys.platform == "win32":
        return _win_send_unicode_string(text, char_delay_ms)
    elif sys.platform == "darwin":
        return _mac_send_string(text)
    else:
        return _linux_send_string(text, char_delay_ms)


# ── Windows ─────────────────────────────────────────────────────

def _win_send_unicode_string(text: str, char_delay_ms: float) -> bool:
    import ctypes
    import ctypes.wintypes

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

    try:
        for char in text:
            code = ord(char)
            inputs = (INPUT * 2)()

            inputs[0].type = INPUT_KEYBOARD
            inputs[0].ki.wVk = 0
            inputs[0].ki.wScan = code
            inputs[0].ki.dwFlags = KEYEVENTF_UNICODE
            inputs[0].ki.time = 0
            inputs[0].ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

            inputs[1].type = INPUT_KEYBOARD
            inputs[1].ki.wVk = 0
            inputs[1].ki.wScan = code
            inputs[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inputs[1].ki.time = 0
            inputs[1].ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

            sent = ctypes.windll.user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
            if sent != 2:
                raise OSError(f"SendInput returned {sent}, expected 2")

            if char_delay_ms > 0:
                time.sleep(char_delay_ms / 1000.0)
        return True
    except Exception:
        logger.exception("SendInput failed")
        return False


# ── macOS ───────────────────────────────────────────────────────

def _mac_send_string(text: str) -> bool:
    """Type text on macOS using osascript."""
    try:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e", f'tell application "System Events" to keystroke "{escaped}"'],
            timeout=10, check=True,
        )
        return True
    except Exception:
        logger.exception("osascript keystroke failed")
        return False


# ── Linux ───────────────────────────────────────────────────────

def _linux_send_string(text: str, char_delay_ms: float) -> bool:
    """Type text on Linux using xdotool or ydotool."""
    try:
        if shutil.which("xdotool"):
            delay_arg = str(int(char_delay_ms)) if char_delay_ms > 0 else "0"
            subprocess.run(
                ["xdotool", "type", "--delay", delay_arg, "--clearmodifiers", text],
                timeout=30, check=True,
            )
            return True
        elif shutil.which("ydotool"):
            subprocess.run(
                ["ydotool", "type", "--", text],
                timeout=30, check=True,
            )
            return True
        else:
            logger.warning("No typing tool found (install xdotool or ydotool)")
            return False
    except Exception:
        logger.exception("Linux text input failed")
        return False
