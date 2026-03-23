"""Windows platform detection and helpers."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32"


def get_windows_version() -> tuple[int, int, int]:
    """Get the Windows version as (major, minor, build).

    Returns (0, 0, 0) if not on Windows or version cannot be determined.
    """
    if not is_windows():
        return (0, 0, 0)
    try:
        ver = sys.getwindowsversion()
        return (ver.major, ver.minor, ver.build)
    except AttributeError:
        return (0, 0, 0)


def check_platform() -> None:
    """Verify we're running on a supported platform.

    Logs a warning if not on Windows. DictateMe is Windows-only for now.
    """
    if not is_windows():
        logger.warning(
            "DictateMe is designed for Windows. Some features may not work on %s.",
            sys.platform,
        )
    else:
        major, minor, build = get_windows_version()
        logger.info("Windows %d.%d (build %d)", major, minor, build)
