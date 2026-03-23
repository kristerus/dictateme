"""LLM provider configuration for litellm."""

from __future__ import annotations

import logging
import os

from ..core.config import LLMConfig

logger = logging.getLogger(__name__)


def get_litellm_model_string(config: LLMConfig) -> str:
    """Build the litellm model identifier string from config.

    litellm uses provider-prefixed model strings, e.g.:
    - "ollama/llama3.2:3b"
    - "gpt-4o-mini" (OpenAI is the default, no prefix needed)
    - "anthropic/claude-sonnet-4-20250514"

    Returns:
        A model string suitable for litellm.completion().
    """
    provider = config.provider.lower()

    if provider == "ollama":
        return f"ollama/{config.ollama.model}"
    elif provider == "openai":
        return config.openai.model
    elif provider == "anthropic":
        return f"anthropic/{config.anthropic.model}"
    elif provider == "groq":
        return f"groq/{config.groq.model}"
    elif provider == "custom":
        return config.custom.model
    else:
        logger.warning("Unknown LLM provider '%s', using model name directly", provider)
        return provider


def configure_provider_env(config: LLMConfig) -> None:
    """Set environment variables needed by litellm for the configured provider.

    litellm reads API keys from environment variables. This sets them
    from the user's config so they don't need to be in the system env.
    """
    provider = config.provider.lower()

    if provider == "ollama":
        os.environ.setdefault("OLLAMA_API_BASE", config.ollama.base_url)
    elif provider == "openai" and config.openai.api_key:
        os.environ.setdefault("OPENAI_API_KEY", config.openai.api_key)
    elif provider == "anthropic" and config.anthropic.api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", config.anthropic.api_key)
    elif provider == "groq" and config.groq.api_key:
        os.environ.setdefault("GROQ_API_KEY", config.groq.api_key)
    elif provider == "custom":
        if config.custom.api_key:
            os.environ.setdefault("OPENAI_API_KEY", config.custom.api_key)
        if config.custom.base_url:
            os.environ.setdefault("OPENAI_API_BASE", config.custom.base_url)


def get_litellm_kwargs(config: LLMConfig) -> dict:
    """Build extra kwargs for litellm.completion() based on provider.

    Returns:
        Dict of kwargs to pass to litellm.acompletion().
    """
    provider = config.provider.lower()
    kwargs: dict = {}

    if provider == "ollama":
        kwargs["api_base"] = config.ollama.base_url
    elif provider == "custom" and config.custom.base_url:
        kwargs["api_base"] = config.custom.base_url

    return kwargs
