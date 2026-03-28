"""LLM text processing: cleanup and reformatting via direct API calls."""

from __future__ import annotations

import logging
import time

from ..core.config import AppConfig
from ..core.types import ProcessedText, ProcessingContext, TextFormat
from .prompts import build_cleanup_prompt, build_reformat_prompt
from .providers import chat_completion

logger = logging.getLogger(__name__)


class LLMProcessor:
    """LLM text processor using direct provider API calls."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @property
    def is_enabled(self) -> bool:
        return self._config.llm.enabled

    async def cleanup(
        self,
        raw_transcript: str,
        context: ProcessingContext,
        language: str = "en",
    ) -> ProcessedText:
        """Clean up raw transcription: remove fillers, fix grammar, punctuate."""
        system_prompt = build_cleanup_prompt(context, language=language)

        t0 = time.perf_counter()
        response = await chat_completion(
            self._config.llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_transcript},
            ],
            temperature=0.3,
            max_tokens=len(raw_transcript) * 3,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        logger.info("LLM cleanup: %d chars -> %d chars in %.0fms", len(raw_transcript), len(response.text), elapsed_ms)

        return ProcessedText(
            text=response.text,
            format_applied=TextFormat.AS_IS,
            model_used=response.model,
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
        """Reformat already-cleaned text into a specific style."""
        if target_format == TextFormat.AS_IS:
            return ProcessedText(
                text=text,
                format_applied=TextFormat.AS_IS,
                model_used="none",
                latency_ms=0,
            )

        system_prompt = build_reformat_prompt(
            target_format,
            custom_instruction=custom_instruction,
            format_presets=self._config.formatting.presets,
            language=language,
        )

        t0 = time.perf_counter()
        response = await chat_completion(
            self._config.llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=len(text) * 3,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        logger.info("LLM reformat (%s): %.0fms", target_format.value, elapsed_ms)

        return ProcessedText(
            text=response.text,
            format_applied=target_format,
            model_used=response.model,
            latency_ms=elapsed_ms,
        )
