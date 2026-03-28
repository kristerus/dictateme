"""faster-whisper STT engine implementation."""

from __future__ import annotations

import logging
import time

import numpy as np

from ..core.types import TranscriptionResult, TranscriptionSegment
from .model_manager import resolve_compute_type, resolve_device

logger = logging.getLogger(__name__)


class FasterWhisperEngine:
    """Speech-to-text engine using faster-whisper (CTranslate2 backend).

    Thread-safe for concurrent transcribe() calls (faster-whisper
    handles this internally).
    """

    def __init__(self, beam_size: int = 5) -> None:
        self._model = None
        self._model_name: str = ""
        self._device: str = "cpu"
        self._beam_size = beam_size

    def load_model(
        self,
        model_name: str,
        device: str = "auto",
        compute_type: str = "float16",
    ) -> None:
        """Load a faster-whisper model.

        Args:
            model_name: Model size (e.g., 'small.en', 'medium.en').
            device: 'auto', 'cuda', or 'cpu'.
            compute_type: 'float16', 'int8', or 'float32'.
        """
        from faster_whisper import WhisperModel

        self._device = resolve_device(device)
        ct = resolve_compute_type(compute_type, self._device)

        logger.info(
            "Loading faster-whisper model '%s' on %s (%s)...",
            model_name, self._device, ct,
        )

        t0 = time.perf_counter()
        self._model = WhisperModel(
            model_name,
            device=self._device,
            compute_type=ct,
        )
        self._model_name = model_name
        elapsed = time.perf_counter() - t0

        logger.info("Model loaded in %.1fs", elapsed)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio using faster-whisper.

        Args:
            audio: float32 numpy array, mono, [-1.0, 1.0].
            sample_rate: Sample rate (must be 16000 for Whisper).
            language: Language code (e.g. "en", "de", "ja") to force.
                      None or "auto" = auto-detect.

        Returns:
            TranscriptionResult with text, segments, and metadata.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        t0 = time.perf_counter()

        # None means auto-detect; "auto" is our config convention
        lang_hint = language if language and language != "auto" else None

        segments_iter, info = self._model.transcribe(
            audio,
            beam_size=self._beam_size,
            language=lang_hint,
            vad_filter=False,  # We do our own VAD
        )

        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []

        for seg in segments_iter:
            segments.append(
                TranscriptionSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    confidence=seg.avg_logprob,
                )
            )
            text_parts.append(seg.text)

        full_text = "".join(text_parts).strip()
        duration = len(audio) / sample_rate
        elapsed = time.perf_counter() - t0

        logger.info(
            "Transcription complete: %.1fs audio in %.1fs (%.1fx realtime)",
            duration, elapsed, duration / elapsed if elapsed > 0 else 0,
        )

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            confidence=info.language_probability,
            duration_seconds=duration,
            segments=segments,
        )

    def unload_model(self) -> None:
        """Free model resources."""
        self._model = None
        self._model_name = ""
        logger.info("Model unloaded")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name
