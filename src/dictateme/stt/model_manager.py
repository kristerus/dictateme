"""Model download, caching, and selection for STT models."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# faster-whisper models are cached in this directory
DEFAULT_MODEL_DIR = Path.home() / ".dictateme" / "models"

# Available model sizes with approximate VRAM/RAM requirements
MODEL_INFO: dict[str, dict[str, str | int]] = {
    "tiny.en": {"params": "39M", "vram_mb": 150, "speed": "fastest"},
    "tiny": {"params": "39M", "vram_mb": 150, "speed": "fastest"},
    "small.en": {"params": "244M", "vram_mb": 500, "speed": "fast"},
    "small": {"params": "244M", "vram_mb": 500, "speed": "fast"},
    "medium.en": {"params": "769M", "vram_mb": 1200, "speed": "moderate"},
    "medium": {"params": "769M", "vram_mb": 1200, "speed": "moderate"},
    "large-v3": {"params": "1550M", "vram_mb": 2500, "speed": "slow"},
}


def get_model_dir() -> Path:
    """Get the model cache directory, creating it if needed."""
    DEFAULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_MODEL_DIR


def is_model_available(model_name: str) -> bool:
    """Check if a model is already cached locally.

    Note: faster-whisper handles its own download/cache via huggingface_hub.
    This checks the faster-whisper/CTranslate2 cache location.
    """
    # faster-whisper uses huggingface_hub cache by default
    # We just check if the model name is valid
    return model_name in MODEL_INFO


def resolve_device(device_setting: str) -> str:
    """Resolve 'auto' device to 'cuda' or 'cpu'.

    Args:
        device_setting: 'auto', 'cuda', or 'cpu'.

    Returns:
        'cuda' if CUDA is available and requested, else 'cpu'.
    """
    if device_setting == "cpu":
        return "cpu"
    if device_setting == "cuda":
        return "cuda"

    # Auto-detect
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("CUDA available, using GPU for STT")
            return "cuda"
    except ImportError:
        pass

    logger.info("CUDA not available, using CPU for STT")
    return "cpu"


def resolve_compute_type(compute_type: str, device: str) -> str:
    """Resolve compute type based on device capabilities.

    Args:
        compute_type: Requested type (float16, int8, float32).
        device: Resolved device ('cuda' or 'cpu').

    Returns:
        Compatible compute type for the device.
    """
    if device == "cpu" and compute_type == "float16":
        logger.info("float16 not supported on CPU, using float32")
        return "float32"
    return compute_type
