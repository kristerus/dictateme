"""Direct HTTP LLM provider calls - no third-party dependencies."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.request import Request, urlopen

from ..core.config import LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Minimal response from an LLM chat completion."""
    text: str
    model: str


def _post_json(url: str, body: dict, headers: dict, timeout: float = 30.0) -> dict:
    """POST JSON and return parsed response."""
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


async def chat_completion(
    config: LLMConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> ChatResponse:
    """Send a chat completion request to the configured LLM provider.

    Runs the blocking HTTP call in a thread to stay async-compatible.
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _chat_completion_sync, config, messages, temperature, max_tokens
    )


def _chat_completion_sync(
    config: LLMConfig,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> ChatResponse:
    """Synchronous chat completion dispatch to the right provider."""
    provider = config.provider.lower()

    if provider == "ollama":
        return _ollama(config, messages, temperature, max_tokens)
    elif provider == "anthropic":
        return _anthropic(config, messages, temperature, max_tokens)
    elif provider == "openai":
        return _openai_compat(
            config.openai.base_url or "https://api.openai.com/v1",
            config.openai.api_key,
            config.openai.model,
            messages, temperature, max_tokens,
        )
    elif provider == "groq":
        return _openai_compat(
            config.groq.base_url or "https://api.groq.com/openai/v1",
            config.groq.api_key,
            config.groq.model,
            messages, temperature, max_tokens,
        )
    elif provider == "custom":
        return _openai_compat(
            config.custom.base_url,
            config.custom.api_key,
            config.custom.model,
            messages, temperature, max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _ollama(
    config: LLMConfig,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> ChatResponse:
    """Ollama uses its own chat API format."""
    base = config.ollama.base_url.rstrip("/")
    url = f"{base}/api/chat"
    body = {
        "model": config.ollama.model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    resp = _post_json(url, body, {}, timeout=60.0)
    text = resp.get("message", {}).get("content", "")
    return ChatResponse(text=text.strip(), model=config.ollama.model)


def _openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> ChatResponse:
    """OpenAI-compatible API (also works for Groq, custom endpoints)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = _post_json(url, body, headers, timeout=30.0)
    text = resp["choices"][0]["message"]["content"]
    return ChatResponse(text=text.strip(), model=model)


def _anthropic(
    config: LLMConfig,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> ChatResponse:
    """Anthropic Messages API (different format from OpenAI)."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": config.anthropic.api_key,
        "anthropic-version": "2023-06-01",
    }

    # Anthropic separates system from user messages
    system_text = ""
    user_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            user_messages.append(msg)

    body = {
        "model": config.anthropic.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": user_messages,
    }
    if system_text:
        body["system"] = system_text

    resp = _post_json(url, body, headers, timeout=30.0)
    text = resp["content"][0]["text"]
    return ChatResponse(text=text.strip(), model=config.anthropic.model)
