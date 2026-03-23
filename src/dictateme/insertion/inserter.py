"""Text insertion coordinator.

Chooses the best insertion method based on configuration and
the active window, then inserts text.
"""

from __future__ import annotations

import logging

from ..core.config import InsertionConfig
from ..core.types import ActiveWindowInfo, InsertionMethod
from .clipboard import clipboard_paste
from .context import get_active_window
from .sendinput import send_unicode_string

logger = logging.getLogger(__name__)

# Applications known to need SendInput instead of clipboard paste
SENDINPUT_APPS = frozenset({
    "WindowsTerminal.exe",
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "ConEmu64.exe",
    "mintty.exe",
})


class TextInserter:
    """Coordinates text insertion into the active application."""

    def __init__(self, config: InsertionConfig) -> None:
        self._config = config

    def get_active_window(self) -> ActiveWindowInfo:
        """Snapshot the currently focused window."""
        return get_active_window()

    def insert_text(
        self,
        text: str,
        window: ActiveWindowInfo | None = None,
        method: InsertionMethod | None = None,
    ) -> bool:
        """Insert text into the target window.

        Args:
            text: Text to insert.
            window: Target window info (captures current if None).
            method: Override insertion method (uses config/auto if None).

        Returns:
            True on success.
        """
        if not text:
            return True

        if window is None:
            window = self.get_active_window()

        if method is None:
            method = self._resolve_method(window)

        logger.info(
            "Inserting %d chars into '%s' via %s",
            len(text), window.process_name, method.value,
        )

        if method == InsertionMethod.CLIPBOARD_PASTE:
            return clipboard_paste(
                text,
                restore=self._config.restore_clipboard,
                restore_delay_ms=self._config.clipboard_restore_delay_ms,
            )
        elif method == InsertionMethod.SEND_INPUT_UNICODE:
            return send_unicode_string(text)
        else:
            logger.warning("UI Automation not yet implemented, falling back to clipboard")
            return clipboard_paste(
                text,
                restore=self._config.restore_clipboard,
                restore_delay_ms=self._config.clipboard_restore_delay_ms,
            )

    def _resolve_method(self, window: ActiveWindowInfo) -> InsertionMethod:
        """Choose the best insertion method for the given window."""
        config_method = self._config.method.lower()

        if config_method == "sendinput":
            return InsertionMethod.SEND_INPUT_UNICODE
        elif config_method == "clipboard_paste":
            return InsertionMethod.CLIPBOARD_PASTE
        elif config_method == "auto":
            if window.process_name in SENDINPUT_APPS:
                return InsertionMethod.SEND_INPUT_UNICODE
            return InsertionMethod.CLIPBOARD_PASTE
        else:
            return InsertionMethod.CLIPBOARD_PASTE
