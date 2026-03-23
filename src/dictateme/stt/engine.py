"""Speech-to-text engine protocol and types."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from ..core.types import TranscriptionResult


class STTEngine(Protocol):
    """Protocol for speech-to-text engines.

    Implementations must be thread-safe. The engine is initialized once
    and called from the orchestrator's processing thread.
    """

    def load_model(self, model_name: str, device: str = "auto") -> None:
        """Load a model. Blocks until ready. Call once at startup."""
        ...

    def transcribe(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> TranscriptionResult:
        """Transcribe a complete audio buffer.

        Args:
            audio: float32 numpy array, mono, normalized to [-1.0, 1.0].
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            TranscriptionResult with full text and segments.
        """
        ...

    def unload_model(self) -> None:
        """Free model resources."""
        ...

    @property
    def is_loaded(self) -> bool:
        """Whether a model is currently loaded and ready."""
        ...
