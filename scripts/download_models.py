"""Pre-download Whisper models for offline use.

Downloads the specified faster-whisper model to the local cache
so DictateMe can work without an internet connection.

Usage:
    python scripts/download_models.py              # Downloads default (small.en)
    python scripts/download_models.py tiny.en      # Downloads tiny.en
    python scripts/download_models.py --all        # Downloads all English models
"""

from __future__ import annotations

import sys


MODELS = {
    "tiny.en": "Tiny English (fastest, ~75 MB)",
    "small.en": "Small English (recommended, ~500 MB)",
    "medium.en": "Medium English (high accuracy, ~1.5 GB)",
    "large-v3": "Large v3 (best accuracy, ~3 GB, multilingual)",
}


def download_model(model_name: str) -> None:
    """Download a faster-whisper model."""
    from faster_whisper import WhisperModel

    print(f"\nDownloading '{model_name}'...")
    print(f"  Description: {MODELS.get(model_name, 'Unknown model')}")
    print("  This may take a few minutes on first download.\n")

    # Loading the model triggers the download
    model = WhisperModel(model_name, device="cpu", compute_type="float32")
    del model

    print(f"\n  Model '{model_name}' downloaded and cached.")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        for name in MODELS:
            download_model(name)
    elif len(sys.argv) > 1:
        model = sys.argv[1]
        if model not in MODELS:
            print(f"Unknown model: {model}")
            print(f"Available: {', '.join(MODELS.keys())}")
            sys.exit(1)
        download_model(model)
    else:
        download_model("small.en")

    print("\nDone! Models are cached and ready for offline use.")


if __name__ == "__main__":
    main()
