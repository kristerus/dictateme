"""HTTP API server for the DictateMe Tauri sidecar.

Exposes the STT/LLM pipeline as HTTP endpoints for the Tauri desktop
app to call over localhost. Uses Python's built-in http.server so no
extra web framework dependency is needed.

Endpoints:
    POST /start_recording  - Begin microphone capture
    POST /stop_recording   - Stop capture, transcribe, optional LLM cleanup
    POST /cancel_recording - Stop capture and discard audio (no transcription)
    POST /reformat         - Reformat text via LLM
    POST /insert           - Insert text into the active window
    GET  /settings         - Return current config as JSON
    POST /settings         - Save config to ~/.dictateme/config.toml
    GET  /status           - Health check / component status
    GET  /audio_devices    - List available audio input devices

Run directly:
    python -m dictateme.server

Or via entry point (add to pyproject.toml [project.scripts]):
    # dictateme-server = "dictateme.server:main"
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .audio.capture import AudioCapture
from .core.config import (
    USER_CONFIG_DIR,
    USER_CONFIG_PATH,
    AppConfig,
    load_config,
)
from .core.event_bus import EventBus
from .core.types import ProcessingContext, TextFormat
from .insertion.context import get_active_window
from .insertion.inserter import TextInserter
from .llm.processor import LiteLLMProcessor
from .audio.devices import list_input_devices
from .stt.faster_whisper import FasterWhisperEngine

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 18234


# ---------------------------------------------------------------------------
# Shared application state (module-level singleton)
# ---------------------------------------------------------------------------

class _AppState:
    """Holds all initialised components so request handlers can access them."""

    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.event_bus: EventBus | None = None
        self.audio: AudioCapture | None = None
        self.stt: FasterWhisperEngine | None = None
        self.llm: LiteLLMProcessor | None = None
        self.inserter: TextInserter | None = None
        self.model_loaded = False
        self.model_loading = False


_state = _AppState()


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class DictateMeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for all DictateMe API endpoints."""

    # Silence the default stderr request log; we do our own logging.
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        logger.debug("HTTP %s", format % args)

    # -- helpers ------------------------------------------------------------

    def _send_json(
        self,
        data: dict,
        status: int = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {exc}")
            return None

    # -- CORS preflight -----------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    # -- routing ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/status":
            self._handle_status()
        elif self.path == "/settings":
            self._handle_get_settings()
        elif self.path == "/audio_devices":
            self._handle_audio_devices()
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/start_recording":
            self._handle_start_recording()
        elif self.path == "/stop_recording":
            self._handle_stop_recording()
        elif self.path == "/reformat":
            self._handle_reformat()
        elif self.path == "/insert":
            self._handle_insert()
        elif self.path == "/cancel_recording":
            self._handle_cancel_recording()
        elif self.path == "/settings":
            self._handle_post_settings()
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")

    # -- endpoint implementations -------------------------------------------

    def _handle_status(self) -> None:
        recording = _state.audio.is_recording if _state.audio else False
        self._send_json({
            "status": "ready",
            "model_loaded": _state.model_loaded,
            "model_loading": _state.model_loading,
            "recording": recording,
        })

    def _handle_get_settings(self) -> None:
        if _state.config is None:
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, "Config not loaded"
            )
            return
        self._send_json(asdict(_state.config))

    def _handle_audio_devices(self) -> None:
        try:
            devices = list_input_devices()
            self._send_json({"devices": [asdict(d) for d in devices]})
        except Exception:
            logger.exception("Failed to list audio devices")
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Failed to list audio devices",
            )

    def _handle_post_settings(self) -> None:
        body = self._read_json_body()
        if body is None:
            return  # error already sent

        # Write TOML config.  Use tomli_w if available, else minimal fallback.
        try:
            import tomli_w
            toml_bytes = tomli_w.dumps(body).encode("utf-8") if isinstance(body, dict) else b""
        except ImportError:
            toml_bytes = _dict_to_toml(body).encode("utf-8")

        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        USER_CONFIG_PATH.write_bytes(toml_bytes)
        logger.info("Saved user config to %s", USER_CONFIG_PATH)

        # Reload config in memory
        _state.config = load_config()

        self._send_json({"status": "saved"})

    def _handle_start_recording(self) -> None:
        if _state.audio is None:
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE, "Audio not initialised"
            )
            return

        _state.audio.start_recording()
        logger.info("Recording started via API")
        self._send_json({"status": "recording"})

    def _handle_cancel_recording(self) -> None:
        if _state.audio is not None and _state.audio.is_recording:
            _state.audio.stop_recording()  # discard the audio data
            logger.info("Recording cancelled via API")
            self._send_json({"status": "cancelled"})
        else:
            self._send_json({"status": "not_recording"})

    def _handle_stop_recording(self) -> None:
        if _state.audio is None or _state.stt is None:
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Audio or STT not initialised",
            )
            return

        if not _state.audio.is_recording:
            self._send_error_json(
                HTTPStatus.CONFLICT, "Not currently recording"
            )
            return

        # Stop capture and retrieve audio data
        audio = _state.audio.stop_recording()
        sample_rate = _state.config.audio.sample_rate if _state.config else 16000
        duration = len(audio) / sample_rate

        if len(audio) == 0:
            self._send_json({"text": "", "raw": "", "duration": 0.0})
            return

        # Transcribe via faster-whisper
        if not _state.model_loaded:
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE, "STT model not loaded yet"
            )
            return

        # Pass language hint from config (None/"auto" = auto-detect)
        lang_hint = _state.config.general.language if _state.config else "auto"
        result = _state.stt.transcribe(
            audio, sample_rate=sample_rate, language=lang_hint,
        )
        raw_text = result.text
        detected_lang = result.language  # e.g. "en", "de", "ja"

        # Optional LLM cleanup (language-aware)
        cleaned_text = raw_text
        if (
            _state.llm is not None
            and _state.llm.is_enabled
            and raw_text.strip()
        ):
            try:
                window = get_active_window()
                ctx = ProcessingContext(
                    app_name=window.process_name,
                    window_title=window.title,
                )
                loop = asyncio.new_event_loop()
                try:
                    processed = loop.run_until_complete(
                        _state.llm.cleanup(raw_text, ctx, language=detected_lang)
                    )
                    cleaned_text = processed.text
                finally:
                    loop.close()
            except Exception:
                logger.exception("LLM cleanup failed, returning raw transcript")

        logger.info(
            "Stop recording -> %d chars (%.1fs audio, lang=%s)",
            len(cleaned_text), duration, detected_lang,
        )
        self._send_json({
            "text": cleaned_text,
            "raw": raw_text,
            "duration": round(duration, 2),
            "language": detected_lang,
        })

    def _handle_reformat(self) -> None:
        body = self._read_json_body()
        if body is None:
            return

        text = body.get("text", "")
        fmt_str = body.get("format", "as_is")
        custom_instruction = body.get("custom_instruction")
        language = body.get("language", "en")

        if not text:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Missing text field")
            return

        if _state.llm is None or not _state.llm.is_enabled:
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE, "LLM not enabled"
            )
            return

        # Resolve the TextFormat enum
        try:
            target_format = TextFormat(fmt_str)
        except ValueError:
            valid = [f.value for f in TextFormat]
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                f"Unknown format: {fmt_str!r}. Valid: {valid}",
            )
            return

        window = get_active_window()
        ctx = ProcessingContext(
            app_name=window.process_name,
            window_title=window.title,
        )

        loop = asyncio.new_event_loop()
        try:
            processed = loop.run_until_complete(
                _state.llm.reformat(
                    text,
                    target_format,
                    ctx,
                    custom_instruction=custom_instruction,
                    language=language,
                )
            )
        except Exception:
            logger.exception("LLM reformat failed")
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, "LLM reformat failed"
            )
            return
        finally:
            loop.close()

        self._send_json({"text": processed.text})

    def _handle_insert(self) -> None:
        body = self._read_json_body()
        if body is None:
            return

        text = body.get("text", "")
        if not text:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Missing text field")
            return

        if _state.inserter is None:
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE, "Inserter not initialised"
            )
            return

        ok = _state.inserter.insert_text(text)
        if ok:
            self._send_json({"status": "ok"})
        else:
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, "Insertion failed"
            )


# ---------------------------------------------------------------------------
# Minimal TOML serializer (fallback when tomli_w is unavailable)
# ---------------------------------------------------------------------------

def _dict_to_toml(data: dict, prefix: str = "") -> str:
    """Very simple dict -> TOML string for flat/nested dicts of primitives."""
    lines: list[str] = []
    sub_tables: list[tuple[str, dict]] = []

    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            sub_tables.append((full_key, value))
        else:
            lines.append(f"{key} = {_toml_value(value)}")

    result = "\n".join(lines)
    for table_key, table_dict in sub_tables:
        section = _dict_to_toml(table_dict, prefix=table_key)
        result += f"\n\n[{table_key}]\n{section}"

    return result


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        items = ", ".join(_toml_value(v) for v in value)
        return f"[{items}]"
    return repr(value)


# ---------------------------------------------------------------------------
# Startup / initialisation
# ---------------------------------------------------------------------------

def _load_model_background() -> None:
    """Load the STT model in a background thread."""
    _state.model_loading = True
    try:
        cfg = _state.config
        assert cfg is not None
        assert _state.stt is not None
        _state.stt.load_model(
            model_name=cfg.stt.model,
            device=cfg.stt.device,
            compute_type=cfg.stt.compute_type,
        )
        _state.model_loaded = True
        logger.info("STT model loaded successfully")
    except Exception:
        logger.exception("Failed to load STT model")
    finally:
        _state.model_loading = False


def _initialise_components() -> None:
    """Create and wire up all pipeline components."""
    logger.info("Loading configuration...")
    _state.config = load_config()
    cfg = _state.config

    logger.info("Creating event bus...")
    _state.event_bus = EventBus()

    # Audio capture
    logger.info("Initialising audio capture...")
    _state.audio = AudioCapture(
        config=cfg.audio,
        event_bus=_state.event_bus,
        max_recording_seconds=cfg.general.max_recording_seconds,
    )
    try:
        _state.audio.initialize()
    except Exception:
        logger.exception(
            "Audio capture init failed (microphone may be unavailable). "
            "Recording endpoints will return errors."
        )
        _state.audio = None

    # STT engine
    logger.info("Creating STT engine...")
    _state.stt = FasterWhisperEngine(beam_size=cfg.stt.beam_size)

    # Start model loading in background
    logger.info("Starting background model load...")
    model_thread = threading.Thread(
        target=_load_model_background, daemon=True, name="stt-model-loader"
    )
    model_thread.start()

    # LLM processor
    if cfg.llm.enabled:
        logger.info("Creating LLM processor (provider=%s)...", cfg.llm.provider)
        try:
            _state.llm = LiteLLMProcessor(config=cfg)
        except Exception:
            logger.exception("LLM processor init failed; LLM features disabled")
            _state.llm = None
    else:
        logger.info("LLM processing disabled in config")

    # Text inserter
    logger.info("Creating text inserter...")
    _state.inserter = TextInserter(config=cfg.insertion)

    logger.info("All components initialised")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the DictateMe HTTP API server."""
    # Configure logging to stderr
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info("DictateMe server starting on %s:%d", HOST, PORT)

    _initialise_components()

    server = HTTPServer((HOST, PORT), DictateMeHandler)
    logger.info("Listening on http://%s:%d", HOST, PORT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.server_close()
        if _state.audio is not None:
            _state.audio.shutdown()
        if _state.stt is not None:
            _state.stt.unload_model()
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
