"""System prompts and format templates for LLM processing."""

from __future__ import annotations

from ..core.types import ProcessingContext, TextFormat

CLEANUP_SYSTEM_PROMPT = """\
You are a dictation assistant. Your job is to clean up speech-to-text \
transcription output and produce polished written text.

Rules:
1. Remove filler words (um, uh, like, you know, so, basically).
2. Fix grammar and punctuation.
3. Preserve the speaker's intent and meaning exactly.
4. Do not add information that was not in the original speech.
5. Do not summarize or shorten unless the speech was clearly repetitive.
6. Match the appropriate tone for the target application.
7. Return ONLY the cleaned text. No explanations, no quotation marks.

Active application: {app_name}
Window title: {window_title}"""

REFORMAT_SYSTEM_PROMPT = """\
Rewrite the following text in the specified format. Return ONLY the \
reformatted text. No explanations, no quotation marks, no preamble.

Target format: {format_name}
Format instructions: {format_instructions}"""

# Default format instructions (can be overridden by user config)
DEFAULT_FORMAT_INSTRUCTIONS: dict[TextFormat, str] = {
    TextFormat.AS_IS: "",
    TextFormat.FORMAL: "Rewrite in a formal, professional tone. Preserve all meaning.",
    TextFormat.CASUAL: "Rewrite in a casual, friendly tone. Keep it natural.",
    TextFormat.EMAIL: (
        "Format as a professional email body. "
        "Add appropriate greeting/closing if missing."
    ),
    TextFormat.BULLET_POINTS: "Convert into concise bullet points. Use - prefix.",
    TextFormat.CODE_COMMENT: (
        "Rewrite as clear code comments. Use // prefix for each line."
    ),
    TextFormat.AI_PROMPT: (
        "Rewrite as a clear, detailed prompt for an AI assistant."
    ),
    TextFormat.SLACK_MESSAGE: (
        "Rewrite as a concise Slack message. Keep it brief and direct."
    ),
}


def build_cleanup_prompt(context: ProcessingContext) -> str:
    """Build the system prompt for transcript cleanup."""
    return CLEANUP_SYSTEM_PROMPT.format(
        app_name=context.app_name,
        window_title=context.window_title,
    )


def build_reformat_prompt(
    target_format: TextFormat,
    custom_instruction: str | None = None,
    format_presets: dict[str, str] | None = None,
) -> str:
    """Build the system prompt for text reformatting."""
    if custom_instruction:
        instructions = custom_instruction
    elif format_presets and target_format.value in format_presets:
        instructions = format_presets[target_format.value]
    else:
        instructions = DEFAULT_FORMAT_INSTRUCTIONS.get(target_format, "")

    return REFORMAT_SYSTEM_PROMPT.format(
        format_name=target_format.value,
        format_instructions=instructions,
    )
