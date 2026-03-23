"""Microphone audio capture using sounddevice.

Manages the audio input stream, feeds chunks through VAD,
and accumulates speech audio in a ring buffer.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import numpy as np

from .buffer import AudioRingBuffer
from .devices import resolve_device
from .vad import VAD_CHUNK_SAMPLES, VAD_SAMPLE_RATE, NoOpVAD, create_vad

if TYPE_CHECKING:
    from ..core.config import AudioConfig
    from ..core.event_bus import EventBus
    from ..core.events import Event

logger = logging.getLogger(__name__)


class AudioCapture:
    """Manages microphone capture with VAD-based speech detection.

    Opens a sounddevice InputStream and keeps it paused until recording
    is requested. During recording, audio chunks are passed through VAD
    and speech audio is accumulated in a ring buffer.
    """

    def __init__(
        self,
        config: AudioConfig,
        event_bus: EventBus,
        max_recording_seconds: int = 60,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._max_seconds = max_recording_seconds

        self._stream = None
        self._vad = NoOpVAD()
        self._buffer = AudioRingBuffer(max_recording_seconds, config.sample_rate)
        self._recording = False
        self._speech_detected = False
        self._lock = threading.Lock()

        # Accumulate partial chunks until we have enough for VAD
        self._vad_accumulator = np.zeros(0, dtype=np.float32)

    def initialize(self) -> None:
        """Set up the audio stream and VAD. Call once at startup."""
        import sounddevice as sd

        # Initialize VAD
        self._vad = create_vad(self._config.vad_threshold)

        # Resolve device
        device = resolve_device(self._config.device)

        # Open stream (stays active but we only process when recording)
        self._stream = sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=VAD_CHUNK_SAMPLES,
            device=device,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info(
            "Audio stream initialized (device=%s, rate=%d)",
            device or "default",
            self._config.sample_rate,
        )

    def start_recording(self) -> None:
        """Begin capturing audio into the buffer."""
        with self._lock:
            self._buffer.clear()
            self._vad.reset()
            self._vad_accumulator = np.zeros(0, dtype=np.float32)
            self._speech_detected = False
            self._recording = True
        logger.debug("Recording started")

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the captured audio.

        Returns:
            float32 numpy array of captured speech audio.
        """
        with self._lock:
            self._recording = False
            audio = self._buffer.read()
            self._buffer.clear()
        logger.debug(
            "Recording stopped, captured %.2fs of audio",
            len(audio) / self._config.sample_rate,
        )
        return audio

    def shutdown(self) -> None:
        """Stop and close the audio stream."""
        self._recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Audio stream shut down")

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        """sounddevice callback — runs on a real-time audio thread."""
        if status:
            logger.warning("Audio stream status: %s", status)

        if not self._recording:
            return

        # Convert to mono float32
        audio = indata[:, 0].copy()

        # Accumulate for VAD chunk size
        self._vad_accumulator = np.concatenate([self._vad_accumulator, audio])

        while len(self._vad_accumulator) >= VAD_CHUNK_SAMPLES:
            chunk = self._vad_accumulator[:VAD_CHUNK_SAMPLES]
            self._vad_accumulator = self._vad_accumulator[VAD_CHUNK_SAMPLES:]

            prob = self._vad.is_speech(chunk)
            is_speech = prob >= self._vad.threshold

            if is_speech:
                if not self._speech_detected:
                    self._speech_detected = True
                    from ..core.events import Event, EventType
                    self._event_bus.emit(Event(type=EventType.VAD_SPEECH_START))

                self._buffer.write(chunk)

            elif self._speech_detected:
                # Include some trailing silence for natural speech
                self._buffer.write(chunk)

        # Safety: check buffer capacity
        if self._buffer.is_full:
            logger.warning("Audio buffer full, stopping recording")
            self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def buffer_duration(self) -> float:
        return self._buffer.duration_seconds
