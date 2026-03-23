"""System tray icon using pystray.

Provides the always-visible entry point for DictateMe. Shows status,
context menu for settings/quit, and dynamically updates the icon
based on application state.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import pystray

from .icons import create_icon

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


class SystemTray:
    """System tray icon manager.

    Runs pystray in its own thread. Provides methods to update
    the icon state and show notifications.
    """

    def __init__(
        self,
        on_quit: Callable[[], None] | None = None,
        on_settings: Callable[[], None] | None = None,
    ) -> None:
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._state = "loading"

    def start(self) -> None:
        """Create and show the system tray icon.

        Runs pystray's event loop in a daemon thread so it doesn't
        block the main thread.
        """
        menu = pystray.Menu(
            pystray.MenuItem("DictateMe", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status: Starting...", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings", self._handle_settings),
            pystray.MenuItem("Quit", self._handle_quit),
        )

        self._icon = pystray.Icon(
            name="dictateme",
            icon=create_icon("loading"),
            title="DictateMe - Loading...",
            menu=menu,
        )

        self._thread = threading.Thread(
            target=self._icon.run, name="tray", daemon=True
        )
        self._thread.start()
        logger.info("System tray icon started")

    def set_state(self, state: str) -> None:
        """Update the tray icon to reflect the current state.

        Args:
            state: One of 'idle', 'recording', 'processing', 'loading'.
        """
        self._state = state
        if self._icon is None:
            return

        titles = {
            "idle": "DictateMe - Ready",
            "recording": "DictateMe - Recording...",
            "processing": "DictateMe - Processing...",
            "loading": "DictateMe - Loading...",
        }

        self._icon.icon = create_icon(state)
        self._icon.title = titles.get(state, f"DictateMe - {state}")

    def stop(self) -> None:
        """Remove the tray icon and stop the event loop."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        logger.info("System tray icon stopped")

    def _handle_quit(self, icon: object, item: object) -> None:
        if self._on_quit:
            self._on_quit()
        self.stop()

    def _handle_settings(self, icon: object, item: object) -> None:
        if self._on_settings:
            self._on_settings()
