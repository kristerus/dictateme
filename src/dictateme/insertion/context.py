"""Cross-platform active window detection.

Backends:
  - Windows: Win32 API (GetForegroundWindow)
  - macOS:   NSWorkspace via osascript
  - Linux:   xdotool / xprop (X11), swaymsg (Wayland)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

from ..core.types import ActiveWindowInfo

logger = logging.getLogger(__name__)


def get_active_window() -> ActiveWindowInfo:
    """Snapshot the currently focused window (cross-platform)."""
    if sys.platform == "win32":
        return _win_get_active_window()
    elif sys.platform == "darwin":
        return _mac_get_active_window()
    else:
        return _linux_get_active_window()


# ── Windows ─────────────────────────────────────────────────────

def _win_get_active_window() -> ActiveWindowInfo:
    import ctypes
    import ctypes.wintypes

    import psutil
    import win32api
    import win32process

    hwnd = ctypes.windll.user32.GetForegroundWindow()

    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, length + 1)
    title = title_buf.value

    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        process_name = proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        process_name = "unknown"

    is_elevated = False
    try:
        handle = win32api.OpenProcess(0x0400, False, pid)
        if handle:
            win32api.CloseHandle(handle)
    except Exception:
        is_elevated = True

    return ActiveWindowInfo(
        hwnd=hwnd,
        title=title,
        process_name=process_name,
        process_id=pid,
        is_elevated=is_elevated,
    )


# ── macOS ───────────────────────────────────────────────────────

def _mac_get_active_window() -> ActiveWindowInfo:
    title = ""
    process_name = ""
    pid = 0

    try:
        # Get frontmost app name
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            process_name = result.stdout.strip()

        # Get window title
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get title of front window of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            title = result.stdout.strip()

        # Get PID
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get unix id of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            pid = int(result.stdout.strip())
    except Exception:
        logger.debug("Failed to get active window info on macOS")

    return ActiveWindowInfo(
        hwnd=0,
        title=title,
        process_name=process_name,
        process_id=pid,
        is_elevated=False,
    )


# ── Linux ───────────────────────────────────────────────────────

def _linux_get_active_window() -> ActiveWindowInfo:
    title = ""
    process_name = ""
    pid = 0
    wid = 0

    try:
        if shutil.which("xdotool"):
            # X11 with xdotool
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                wid = int(result.stdout.strip())

            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                title = result.stdout.strip()

            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowpid"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                pid = int(result.stdout.strip())

            if pid:
                import psutil
                try:
                    proc = psutil.Process(pid)
                    process_name = proc.name()
                except Exception:
                    process_name = "unknown"
        else:
            logger.debug("xdotool not available for window detection")
    except Exception:
        logger.debug("Failed to get active window info on Linux")

    return ActiveWindowInfo(
        hwnd=wid,
        title=title,
        process_name=process_name,
        process_id=pid,
        is_elevated=False,
    )
