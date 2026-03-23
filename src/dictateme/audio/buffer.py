"""Pre-allocated ring buffer for audio capture.

Uses a fixed numpy array to avoid allocation during recording.
"""

from __future__ import annotations

import numpy as np


class AudioRingBuffer:
    """Fixed-size ring buffer for float32 mono audio samples.

    Args:
        max_seconds: Maximum duration to buffer.
        sample_rate: Audio sample rate in Hz.
    """

    def __init__(self, max_seconds: int = 60, sample_rate: int = 16000) -> None:
        self._capacity = max_seconds * sample_rate
        self._buffer = np.zeros(self._capacity, dtype=np.float32)
        self._write_pos = 0
        self._sample_rate = sample_rate

    @property
    def duration_seconds(self) -> float:
        """Current buffered duration in seconds."""
        return self._write_pos / self._sample_rate

    @property
    def sample_count(self) -> int:
        """Number of samples currently in the buffer."""
        return self._write_pos

    @property
    def is_full(self) -> bool:
        return self._write_pos >= self._capacity

    def write(self, samples: np.ndarray) -> int:
        """Append samples to the buffer.

        Args:
            samples: float32 audio samples to append.

        Returns:
            Number of samples actually written (may be less than input
            if the buffer is nearly full).
        """
        available = self._capacity - self._write_pos
        n = min(len(samples), available)
        if n > 0:
            self._buffer[self._write_pos : self._write_pos + n] = samples[:n]
            self._write_pos += n
        return n

    def read(self) -> np.ndarray:
        """Return a copy of all buffered audio as a float32 array."""
        return self._buffer[: self._write_pos].copy()

    def clear(self) -> None:
        """Reset the buffer to empty (zero-fill for safety)."""
        self._buffer[:self._write_pos] = 0.0
        self._write_pos = 0
