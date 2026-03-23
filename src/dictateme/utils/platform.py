"""Cross-platform detection and helpers."""

from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def get_os_name() -> str:
    if is_windows():
        return "Windows"
    elif is_macos():
        return "macOS"
    elif is_linux():
        return "Linux"
    return sys.platform


def check_platform() -> None:
    """Log platform info at startup."""
    if is_windows():
        try:
            ver = sys.getwindowsversion()
            logger.info("Windows %d.%d (build %d)", ver.major, ver.minor, ver.build)
        except AttributeError:
            logger.info("Windows (version unknown)")
    elif is_macos():
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True, timeout=5,
            )
            logger.info("macOS %s", result.stdout.strip())
        except Exception:
            logger.info("macOS (version unknown)")
    elif is_linux():
        try:
            result = subprocess.run(
                ["uname", "-r"], capture_output=True, text=True, timeout=5,
            )
            logger.info("Linux %s", result.stdout.strip())
        except Exception:
            logger.info("Linux")
    else:
        logger.warning("Unknown platform: %s", sys.platform)


def get_cursor_pos() -> tuple[int, int]:
    """Get the current mouse cursor position (x, y)."""
    if is_windows():
        import ctypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    else:
        # pynput works cross-platform for mouse position
        try:
            from pynput.mouse import Controller
            mouse = Controller()
            return mouse.position
        except Exception:
            return 100, 100


def get_screen_size() -> tuple[int, int]:
    """Get the primary screen dimensions (width, height)."""
    if is_windows():
        import ctypes
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        return w, h
    elif is_macos():
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) == 4:
                    return int(parts[2]), int(parts[3])
        except Exception:
            pass
        # Fallback: use Quartz
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().frame()
            return int(frame.size.width), int(frame.size.height)
        except ImportError:
            pass
        return 1920, 1080
    else:
        # Linux: try xdpyinfo or xrandr
        try:
            result = subprocess.run(
                ["xdpyinfo"], capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "dimensions:" in line:
                    # "  dimensions:    1920x1080 pixels ..."
                    dim = line.split()[1]
                    w, h = dim.split("x")
                    return int(w), int(h)
        except Exception:
            pass
        return 1920, 1080
