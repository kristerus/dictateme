"""Global hotkey registration and management.

Uses the `keyboard` library for system-wide hotkey hooks.
Supports both hold-to-talk and toggle modes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..core.events import Event, EventType
from ..core.types import HotkeyMode
from .bindings import normalize_key_combo

if TYPE_CHECKING:
    from ..core.config import HotkeyConfig
    from ..core.event_bus import EventBus

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Manages global hotkey registration and event dispatch.

    In HOLD mode: emits HOTKEY_PRESSED on key down, HOTKEY_RELEASED on key up.
    In TOGGLE mode: emits HOTKEY_PRESSED on each press (toggles recording).
    """

    def __init__(self, config: HotkeyConfig, event_bus: EventBus) -> None:
        self._config = config
        self._event_bus = event_bus
        self._mode = HotkeyMode(config.mode)
        self._key_combo = normalize_key_combo(config.key_combo)
        self._cancel_key = config.cancel_key
        self._active = False
        self._toggled_on = False
        self._hooks: list = []

    def start(self) -> None:
        """Register global hotkeys. Call once at startup."""
        import keyboard

        if self._mode == HotkeyMode.HOLD:
            # For hold mode, we need key_down and key_up events
            # keyboard library's hook is more suitable for this
            keyboard.on_press_key(
                self._get_trigger_key(),
                self._on_key_down,
                suppress=False,
            )
            keyboard.on_release_key(
                self._get_trigger_key(),
                self._on_key_up,
                suppress=False,
            )
        else:
            # Toggle mode: single press toggles
            keyboard.add_hotkey(
                self._key_combo,
                self._on_toggle_press,
                suppress=False,
            )

        # Cancel key always active
        keyboard.add_hotkey(
            self._cancel_key,
            self._on_cancel,
            suppress=False,
        )

        self._active = True
        logger.info(
            "Hotkey registered: %s (mode=%s, cancel=%s)",
            self._key_combo, self._mode.value, self._cancel_key,
        )

    def stop(self) -> None:
        """Unregister all hotkeys."""
        import keyboard

        keyboard.unhook_all()
        self._active = False
        logger.info("Hotkeys unregistered")

    def _get_trigger_key(self) -> str:
        """Get the primary trigger key from the combo.

        For hold mode with modifiers (e.g., ctrl+windows), we hook
        the last key in the combo and check modifiers manually.
        """
        parts = self._key_combo.split("+")
        return parts[-1] if parts else self._key_combo

    def _check_modifiers(self) -> bool:
        """Check if the required modifier keys are currently held."""
        import keyboard

        parts = self._key_combo.split("+")
        modifiers = parts[:-1]  # All except the trigger key
        for mod in modifiers:
            if not keyboard.is_pressed(mod):
                return False
        return True

    def _on_key_down(self, event: object) -> None:
        """Handle key down in hold mode."""
        if not self._check_modifiers():
            return
        if not self._toggled_on:
            self._toggled_on = True
            self._event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))

    def _on_key_up(self, event: object) -> None:
        """Handle key up in hold mode."""
        if self._toggled_on:
            self._toggled_on = False
            self._event_bus.emit(Event(type=EventType.HOTKEY_RELEASED))

    def _on_toggle_press(self) -> None:
        """Handle press in toggle mode."""
        self._toggled_on = not self._toggled_on
        if self._toggled_on:
            self._event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))
        else:
            self._event_bus.emit(Event(type=EventType.HOTKEY_RELEASED))

    def _on_cancel(self) -> None:
        """Handle cancel key press."""
        if self._toggled_on:
            self._toggled_on = False
        self._event_bus.emit(Event(type=EventType.CANCEL_PRESSED))
