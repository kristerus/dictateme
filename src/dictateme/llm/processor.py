"""LLM text processing: cleanup and reformatting via litellm."""

from __future__ import annotations

import logging
import time

from ..core.config import AppConfig
from ..core.types import ProcessedText, ProcessingContext, TextFormat
from .prompts import build_cleanup_prompt, build_reformat_prompt
from .providers import configure_provider_env, get_litellm_kwargs, get_litellm_model_string

logger = logging.getLogger(__name__)


class LiteLLMProcessor:
    """LLM text processor using litellm for provider-agnostic API calls."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._model_string = get_litellm_model_string(config.llm)
        self._extra_kwargs = get_litellm_kwargs(config.llm)
        configure_provider_env(config.llm)

    @property
    def is_enabled(self) -> bool:
        return self._config.llm.enabled

    async def cleanup(
        self,
        raw_transcript: str,
        context: ProcessingContext,
        language: str = "en",
    ) -> ProcessedText:
        """Clean up raw transcription: remove fillers, fix grammar, punctuate.

        Args:
            raw_transcript: Raw text from STT engine.
            context: Information about the active application.
            language: Detected language code (e.g. "en", "de", "ja").

        Returns:
            ProcessedText with cleaned text.
        """
        import litellm

        system_prompt = build_cleanup_prompt(context, language=language)

        t0 = time.perf_counter()
        response = await litellm.acompletion(
            model=self._model_string,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_transcript},
            ],
            temperature=0.3,
            max_tokens=len(raw_transcript) * 3,  # Generous limit
            **self._extra_kwargs,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        text = response.choices[0].message.content.strip()
        logger.info("LLM cleanup: %d chars -> %d chars in %.0fms", len(raw_transcript), len(text), elapsed_ms)

        return ProcessedText(
            text=text,
            format_applied=TextFormat.AS_IS,
            model_used=self._model_string,
            latency_ms=elapsed_ms,
        )

    async def reformat(
        self,
        text: str,
        target_format: TextFormat,
        context: ProcessingContext,
        custom_instruction: str | None = None,
        language: str = "en",
    ) -> ProcessedText:
        """Reformat already-cleaned text into a specific style.

        Args:
            text: Cleaned text to reformat.
            target_format: Target format preset.
            context: Active application context.
            custom_instruction: Optional custom formatting instruction.
            language: Language code for the text.

        Returns:
            ProcessedText with reformatted text.
        """
        if target_format == TextFormat.AS_IS:
            return ProcessedText(
                text=text,
                format_applied=TextFormat.AS_IS,
                model_used="none",
                latency_ms=0,
            )

        import litellm

        system_prompt = build_reformat_prompt(
            target_format,
            custom_instruction=custom_instruction,
            format_presets=self._config.formatting.presets,
            language=language,
        )

        t0 = time.perf_counter()
        response = await litellm.acompletion(
            model=self._model_string,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=len(text) * 3,
            **self._extra_kwargs,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        result_text = response.choices[0].message.content.strip()
        logger.info("LLM reformat (%s): %.0fms", target_format.value, elapsed_ms)

        return ProcessedText(
            text=result_text,
            format_applied=target_format,
            model_used=self._model_string,
            latency_ms=elapsed_ms,
        )
