"""Structured logging setup for DictateMe."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_DIR = Path.home() / ".dictateme" / "logs"
_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_configured = False


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    Sets up both console (stderr) and file handlers.
    Safe to call multiple times; only configures once.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger for the dictateme namespace
    root = logging.getLogger("dictateme")
    root.setLevel(log_level)

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT))
    root.addHandler(console)

    # File handler
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            _LOG_DIR / "dictateme.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
        )
        root.addHandler(file_handler)
    except OSError:
        root.warning("Could not create log file, logging to console only")
