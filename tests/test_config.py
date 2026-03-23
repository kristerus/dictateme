"""Tests for configuration loading."""

from dictateme.core.config import AppConfig, _apply_dict


def test_default_config_values() -> None:
    """Default config has sensible values."""
    config = AppConfig()
    assert config.general.language == "en"
    assert config.hotkey.mode == "hold"
    assert config.audio.sample_rate == 16000
    assert config.stt.engine == "faster-whisper"
    assert config.stt.model == "small.en"
    assert config.llm.enabled is True
    assert config.llm.provider == "ollama"
    assert config.insertion.method == "clipboard_paste"
    assert config.ui.overlay_position == "cursor"


def test_apply_dict_simple() -> None:
    """_apply_dict sets simple values on a dataclass."""
    config = AppConfig()
    _apply_dict(config.general, {"language": "de", "log_level": "DEBUG"})
    assert config.general.language == "de"
    assert config.general.log_level == "DEBUG"


def test_apply_dict_nested() -> None:
    """_apply_dict recurses into nested dataclasses."""
    config = AppConfig()
    _apply_dict(config, {
        "stt": {"model": "tiny.en", "device": "cpu"},
    })
    assert config.stt.model == "tiny.en"
    assert config.stt.device == "cpu"


def test_apply_dict_unknown_key_ignored() -> None:
    """Unknown keys are silently ignored."""
    config = AppConfig()
    _apply_dict(config, {"nonexistent_key": "value"})
    # Should not raise


def test_apply_dict_presets_merge() -> None:
    """Dict fields (like presets) are merged, not replaced."""
    config = AppConfig()
    _apply_dict(config, {
        "formatting": {
            "presets": {"custom": "Make it fancy."},
        },
    })
    assert config.formatting.presets["custom"] == "Make it fancy."
    # Original presets should still be there
    assert "formal" in config.formatting.presets
