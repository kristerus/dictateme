"""Configuration loading and management.

Loads settings from TOML files with a layered approach:
1. Built-in defaults (config.default.toml shipped with the package)
2. User config (~/.dictateme/config.toml) overrides defaults
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# Resolve paths
_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.default.toml"
USER_CONFIG_DIR = Path.home() / ".dictateme"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.toml"


@dataclass
class HotkeyConfig:
    mode: str = "hold"
    key_combo: str = "ctrl+windows"
    cancel_key: str = "escape"


@dataclass
class AudioConfig:
    device: str = "default"
    sample_rate: int = 16000
    vad_threshold: float = 0.5
    silence_duration_ms: int = 800


@dataclass
class STTConfig:
    engine: str = "faster-whisper"
    model: str = "small.en"
    device: str = "auto"
    compute_type: str = "float16"
    beam_size: int = 5


@dataclass
class LLMProviderConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class LLMConfig:
    enabled: bool = True
    provider: str = "ollama"
    ollama: LLMProviderConfig = field(
        default_factory=lambda: LLMProviderConfig(
            base_url="http://localhost:11434", model="llama3.2:3b"
        )
    )
    openai: LLMProviderConfig = field(
        default_factory=lambda: LLMProviderConfig(model="gpt-4o-mini")
    )
    anthropic: LLMProviderConfig = field(
        default_factory=lambda: LLMProviderConfig(model="claude-sonnet-4-20250514")
    )
    groq: LLMProviderConfig = field(
        default_factory=lambda: LLMProviderConfig(model="llama-3.1-8b-instant")
    )
    custom: LLMProviderConfig = field(default_factory=LLMProviderConfig)


@dataclass
class FormattingConfig:
    auto_insert_delay_ms: int = 1500
    show_preview: bool = True
    default_format: str = "as_is"
    presets: dict[str, str] = field(default_factory=lambda: {
        "formal": "Rewrite in a formal, professional tone. Preserve all meaning.",
        "casual": "Rewrite in a casual, friendly tone. Keep it natural.",
        "email": "Format as a professional email body. Add appropriate greeting/closing if missing.",
        "bullet_points": "Convert into concise bullet points. Use - prefix.",
        "code_comment": "Rewrite as clear code comments. Use // prefix for each line.",
        "ai_prompt": "Rewrite as a clear, detailed prompt for an AI assistant.",
        "slack_message": "Rewrite as a concise Slack message. Keep it brief and direct.",
    })


@dataclass
class InsertionConfig:
    method: str = "clipboard_paste"
    restore_clipboard: bool = True
    clipboard_restore_delay_ms: int = 100


@dataclass
class UIConfig:
    overlay_position: str = "cursor"
    overlay_opacity: float = 0.9
    show_recording_indicator: bool = True
    overlay_width: int = 400


@dataclass
class GeneralConfig:
    language: str = "en"
    start_minimized: bool = True
    auto_start_with_windows: bool = False
    log_level: str = "INFO"
    max_recording_seconds: int = 60


@dataclass
class AppConfig:
    """Top-level application configuration."""

    general: GeneralConfig = field(default_factory=GeneralConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    formatting: FormattingConfig = field(default_factory=FormattingConfig)
    insertion: InsertionConfig = field(default_factory=InsertionConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def _apply_dict(target: object, data: dict) -> None:
    """Recursively apply a dict of values onto a dataclass instance."""
    for key, value in data.items():
        if not hasattr(target, key):
            logger.warning("Unknown config key: %s", key)
            continue
        current = getattr(target, key)
        if isinstance(value, dict) and hasattr(current, "__dataclass_fields__"):
            _apply_dict(current, value)
        elif isinstance(value, dict) and isinstance(current, dict):
            current.update(value)
        else:
            setattr(target, key, value)


def load_config() -> AppConfig:
    """Load configuration with defaults, then overlay user config.

    Returns:
        Fully populated AppConfig instance.
    """
    config = AppConfig()

    # Load built-in defaults
    if DEFAULT_CONFIG_PATH.exists():
        with open(DEFAULT_CONFIG_PATH, "rb") as f:
            defaults = tomllib.load(f)
        _apply_dict(config, defaults)
        logger.debug("Loaded default config from %s", DEFAULT_CONFIG_PATH)

    # Load user overrides
    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH, "rb") as f:
            user = tomllib.load(f)
        _apply_dict(config, user)
        logger.info("Loaded user config from %s", USER_CONFIG_PATH)
    else:
        logger.info("No user config found at %s, using defaults", USER_CONFIG_PATH)

    return config


def ensure_user_config() -> Path:
    """Create the user config directory and copy defaults if needed.

    Returns:
        Path to the user config file.
    """
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not USER_CONFIG_PATH.exists() and DEFAULT_CONFIG_PATH.exists():
        shutil.copy2(DEFAULT_CONFIG_PATH, USER_CONFIG_PATH)
        logger.info("Created user config at %s", USER_CONFIG_PATH)
    return USER_CONFIG_PATH
