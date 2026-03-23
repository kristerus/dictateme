"""Cross-platform global hotkey registration and management.

Uses `pynput` for cross-platform global keyboard hooks.
Supports both hold-to-talk and toggle modes on Windows, macOS, and Linux.

Note: On Linux, pynput requires the user to be in the `input` group
or to run with elevated privileges for global keyboard monitoring.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from ..core.events import Event, EventType
from ..core.types import HotkeyMode
from .bindings import normalize_key_combo

if TYPE_CHECKING:
    from ..core.config import HotkeyConfig
    from ..core.event_bus import EventBus

logger = logging.getLogger(__name__)

# Map key names to pynput Key objects
_SPECIAL_KEYS: dict[str, str] = {
    "ctrl": "ctrl_l",
    "shift": "shift",
    "alt": "alt_l",
    "windows": "cmd" if sys.platform == "darwin" else "cmd_l",
    "cmd": "cmd" if sys.platform == "darwin" else "cmd_l",
    "escape": "esc",
}


class HotkeyManager:
    """Cross-platform global hotkey manager using pynput.

    In HOLD mode: emits HOTKEY_PRESSED on key down, HOTKEY_RELEASED on key up.
    In TOGGLE mode: emits HOTKEY_PRESSED on each press (toggles recording).
    """

    def __init__(self, config: HotkeyConfig, event_bus: EventBus) -> None:
        self._config = config
        self._event_bus = event_bus
        self._mode = HotkeyMode(config.mode)
        self._key_combo = normalize_key_combo(config.key_combo)
        self._cancel_key = config.cancel_key
        self._listener = None
        self._active = False
        self._toggled_on = False

        # Parse the key combo into modifier set + trigger key
        self._modifiers, self._trigger_key = self._parse_combo(self._key_combo)
        self._cancel_pynput_key = self._resolve_key(self._cancel_key)
        self._pressed_keys: set = set()

    def start(self) -> None:
        """Register global hotkeys. Call once at startup."""
        from pynput import keyboard

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        self._active = True

        logger.info(
            "Hotkey registered: %s (mode=%s, cancel=%s)",
            self._key_combo, self._mode.value, self._cancel_key,
        )

    def stop(self) -> None:
        """Unregister all hotkeys."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._active = False
        logger.info("Hotkeys unregistered")

    def _parse_combo(self, combo: str) -> tuple[set[str], str]:
        """Parse 'ctrl+windows' into ({ctrl_l, cmd_l}, 'cmd_l')."""
        parts = combo.split("+")
        if len(parts) == 1:
            return set(), self._resolve_key(parts[0])

        modifiers = set()
        for part in parts[:-1]:
            modifiers.add(self._resolve_key(part))
        trigger = self._resolve_key(parts[-1])
        return modifiers, trigger

    def _resolve_key(self, name: str) -> str:
        """Map a key name to a pynput-compatible identifier."""
        name = name.lower().strip()
        return _SPECIAL_KEYS.get(name, name)

    def _key_to_str(self, key: object) -> str:
        """Convert a pynput key event to a comparable string."""
        from pynput import keyboard

        if isinstance(key, keyboard.Key):
            return key.name
        elif hasattr(key, "char") and key.char:
            return key.char.lower()
        return str(key)

    def _is_trigger(self, key_str: str) -> bool:
        """Check if the given key matches the trigger key."""
        # Handle aliases
        trigger = self._trigger_key
        aliases = {
            "cmd_l": {"cmd_l", "cmd", "cmd_r"},
            "ctrl_l": {"ctrl_l", "ctrl", "ctrl_r"},
            "alt_l": {"alt_l", "alt", "alt_r"},
            "shift": {"shift", "shift_l", "shift_r"},
        }
        if trigger in aliases:
            return key_str in aliases[trigger]
        return key_str == trigger

    def _modifiers_held(self) -> bool:
        """Check if all required modifier keys are currently held."""
        for mod in self._modifiers:
            aliases = {
                "ctrl_l": {"ctrl_l", "ctrl", "ctrl_r"},
                "alt_l": {"alt_l", "alt", "alt_r"},
                "cmd_l": {"cmd_l", "cmd", "cmd_r"},
                "shift": {"shift", "shift_l", "shift_r"},
            }
            expected = aliases.get(mod, {mod})
            if not expected & self._pressed_keys:
                return False
        return True

    def _on_press(self, key: object) -> None:
        key_str = self._key_to_str(key)
        self._pressed_keys.add(key_str)

        # Cancel key
        if key_str == self._cancel_pynput_key or key_str == "esc":
            if self._toggled_on:
                self._toggled_on = False
            self._event_bus.emit(Event(type=EventType.CANCEL_PRESSED))
            return

        # Check trigger
        if not self._is_trigger(key_str):
            return
        if not self._modifiers_held():
            return

        if self._mode == HotkeyMode.HOLD:
            if not self._toggled_on:
                self._toggled_on = True
                self._event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))
        else:
            # Toggle mode
            self._toggled_on = not self._toggled_on
            if self._toggled_on:
                self._event_bus.emit(Event(type=EventType.HOTKEY_PRESSED))
            else:
                self._event_bus.emit(Event(type=EventType.HOTKEY_RELEASED))

    def _on_release(self, key: object) -> None:
        key_str = self._key_to_str(key)
        self._pressed_keys.discard(key_str)

        if self._mode == HotkeyMode.HOLD:
            # Release any key in the combo → stop recording
            if self._toggled_on and (
                self._is_trigger(key_str) or not self._modifiers_held()
            ):
                self._toggled_on = False
                self._event_bus.emit(Event(type=EventType.HOTKEY_RELEASED))
