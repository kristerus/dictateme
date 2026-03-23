"""Tests for the audio ring buffer."""

import numpy as np

from dictateme.audio.buffer import AudioRingBuffer


def test_write_and_read() -> None:
    """Written samples can be read back."""
    buf = AudioRingBuffer(max_seconds=1, sample_rate=16000)
    samples = np.ones(8000, dtype=np.float32) * 0.5
    written = buf.write(samples)

    assert written == 8000
    assert buf.sample_count == 8000
    assert abs(buf.duration_seconds - 0.5) < 0.001

    audio = buf.read()
    assert len(audio) == 8000
    assert np.allclose(audio, 0.5)


def test_buffer_capacity() -> None:
    """Buffer stops accepting samples when full."""
    buf = AudioRingBuffer(max_seconds=1, sample_rate=100)  # 100 samples capacity
    samples = np.ones(150, dtype=np.float32)
    written = buf.write(samples)

    assert written == 100
    assert buf.is_full
    assert buf.sample_count == 100


def test_clear() -> None:
    """Clear resets the buffer."""
    buf = AudioRingBuffer(max_seconds=1, sample_rate=16000)
    buf.write(np.ones(1000, dtype=np.float32))
    buf.clear()

    assert buf.sample_count == 0
    assert buf.duration_seconds == 0.0
    assert not buf.is_full


def test_read_returns_copy() -> None:
    """Read returns a copy, not a view into the buffer."""
    buf = AudioRingBuffer(max_seconds=1, sample_rate=16000)
    buf.write(np.ones(100, dtype=np.float32))

    audio = buf.read()
    audio[:] = 0.0  # Modify the copy

    original = buf.read()
    assert np.allclose(original, 1.0)  # Buffer unchanged
