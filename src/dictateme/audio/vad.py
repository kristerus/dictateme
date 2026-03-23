"""Voice Activity Detection using silero-vad.

Supports both PyTorch (CUDA) and ONNX (CPU-only) backends.
Falls back gracefully if neither is available (no VAD, always treat as speech).
"""

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

# silero-vad expects 16kHz, 512-sample chunks (32ms)
VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SAMPLES = 512


class VADBackend(Protocol):
    """Protocol for VAD implementations."""

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        """Return speech probability (0.0 to 1.0) for a chunk."""
        ...

    def reset(self) -> None:
        """Reset internal state between utterances."""
        ...


class SileroVAD:
    """silero-vad wrapper using PyTorch backend."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._model = None
        self._loaded = False

    def load(self) -> None:
        """Load the silero-vad model. Requires torch."""
        try:
            import torch

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self._model = model
            self._get_speech_timestamps = utils[0]
            self._loaded = True
            logger.info("Loaded silero-vad (PyTorch backend)")
        except ImportError:
            logger.warning("torch not available, silero-vad PyTorch backend disabled")
        except Exception:
            logger.exception("Failed to load silero-vad")

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        """Return speech probability for a 32ms chunk."""
        if not self._loaded or self._model is None:
            return 1.0  # Fallback: assume speech

        import torch

        tensor = torch.from_numpy(audio_chunk).float()
        prob = self._model(tensor, VAD_SAMPLE_RATE).item()
        return prob

    def reset(self) -> None:
        if self._model is not None:
            self._model.reset_states()


class OnnxVAD:
    """silero-vad wrapper using ONNX Runtime backend (no torch dependency)."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._session = None
        self._loaded = False
        self._h = None
        self._c = None

    def load(self) -> None:
        """Load the ONNX silero-vad model."""
        try:
            import onnxruntime as ort

            # The ONNX model should be bundled or downloaded
            model_path = self._find_onnx_model()
            if model_path is None:
                logger.warning("silero-vad ONNX model not found")
                return

            self._session = ort.InferenceSession(str(model_path))
            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)
            self._loaded = True
            logger.info("Loaded silero-vad (ONNX backend)")
        except ImportError:
            logger.warning("onnxruntime not available, ONNX VAD disabled")
        except Exception:
            logger.exception("Failed to load ONNX VAD")

    def _find_onnx_model(self) -> object | None:
        """Locate the silero_vad.onnx model file."""
        from pathlib import Path

        search_paths = [
            Path.home() / ".dictateme" / "models" / "silero_vad.onnx",
            Path(__file__).parent / "silero_vad.onnx",
        ]
        for p in search_paths:
            if p.exists():
                return p
        return None

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        if not self._loaded or self._session is None:
            return 1.0

        input_data = audio_chunk.reshape(1, -1).astype(np.float32)
        sr = np.array([VAD_SAMPLE_RATE], dtype=np.int64)

        ort_inputs = {
            "input": input_data,
            "h": self._h,
            "c": self._c,
            "sr": sr,
        }
        ort_outs = self._session.run(None, ort_inputs)
        prob = ort_outs[0].item()
        self._h = ort_outs[1]
        self._c = ort_outs[2]
        return prob

    def reset(self) -> None:
        if self._loaded:
            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)


class NoOpVAD:
    """Fallback VAD that treats all audio as speech."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        return 1.0

    def reset(self) -> None:
        pass


def create_vad(threshold: float = 0.5) -> SileroVAD | OnnxVAD | NoOpVAD:
    """Create the best available VAD backend.

    Tries PyTorch first, then ONNX, then falls back to NoOpVAD.
    """
    # Try PyTorch
    vad = SileroVAD(threshold)
    vad.load()
    if vad._loaded:
        return vad

    # Try ONNX
    onnx_vad = OnnxVAD(threshold)
    onnx_vad.load()
    if onnx_vad._loaded:
        return onnx_vad

    # Fallback
    logger.warning("No VAD backend available, all audio will be treated as speech")
    return NoOpVAD(threshold)
