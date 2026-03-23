"""Active window detection using Win32 API."""

from __future__ import annotations

import logging

from ..core.types import ActiveWindowInfo

logger = logging.getLogger(__name__)


def get_active_window() -> ActiveWindowInfo:
    """Snapshot the currently focused window.

    Returns:
        ActiveWindowInfo with window handle, title, process info.
    """
    import ctypes
    import ctypes.wintypes

    import psutil
    import win32api
    import win32process

    hwnd = ctypes.windll.user32.GetForegroundWindow()

    # Get window title
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, length + 1)
    title = title_buf.value

    # Get process info
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        process_name = proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        process_name = "unknown"

    # Check if elevated (running as admin)
    is_elevated = False
    try:
        handle = win32api.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
        if handle:
            # If we can open it, it's likely not elevated (or we are elevated too)
            win32api.CloseHandle(handle)
    except Exception:
        is_elevated = True  # Can't open = likely elevated

    return ActiveWindowInfo(
        hwnd=hwnd,
        title=title,
        process_name=process_name,
        process_id=pid,
        is_elevated=is_elevated,
    )
