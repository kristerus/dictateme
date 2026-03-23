"""Audio device enumeration and selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioDevice:
    """Represents an audio input device."""

    index: int
    name: str
    channels: int
    default_sample_rate: float
    is_default: bool


def list_input_devices() -> list[AudioDevice]:
    """List all available audio input devices.

    Returns:
        List of AudioDevice with input capabilities.
    """
    import sounddevice as sd

    devices: list[AudioDevice] = []
    default_input = sd.default.device[0]

    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append(
                AudioDevice(
                    index=i,
                    name=dev["name"],
                    channels=dev["max_input_channels"],
                    default_sample_rate=dev["default_samplerate"],
                    is_default=(i == default_input),
                )
            )

    return devices


def resolve_device(device_setting: str) -> int | None:
    """Resolve a device setting string to a sounddevice device index.

    Args:
        device_setting: "default", a device name substring, or a numeric index.

    Returns:
        Device index for sounddevice, or None for the system default.
    """
    if device_setting == "default":
        return None

    # Try numeric index
    try:
        return int(device_setting)
    except ValueError:
        pass

    # Search by name substring
    for dev in list_input_devices():
        if device_setting.lower() in dev.name.lower():
            logger.info("Resolved audio device '%s' -> [%d] %s", device_setting, dev.index, dev.name)
            return dev.index

    logger.warning("Audio device '%s' not found, using default", device_setting)
    return None
