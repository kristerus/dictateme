"""HTTP API server for the DictateMe Tauri sidecar.

Exposes the STT/LLM pipeline as HTTP endpoints on localhost:18234.
Uses Python's built-in http.server — no web framework dependency.

Run: python -m dictateme.server
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
from .core.config import USER_CONFIG_DIR, USER_CONFIG_PATH, AppConfig, load_config
from .core.event_bus import EventBus
from .core.types import ProcessingContext, TextFormat
from .insertion.context import get_active_window
from .insertion.inserter import TextInserter
from .llm.processor import LiteLLMProcessor
from .stt.faster_whisper import FasterWhisperEngine

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 18234


class _AppState:
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


class DictateMeHandler(BaseHTTPRequestHandler):

    def log_message(self, format: str, *args: object) -> None:
        logger.debug("HTTP %s", format % args)

    def _send_json(self, data: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, msg: str) -> None:
        self._send_json({"error": msg}, status=status)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            self._send_error(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {e}")
            return None

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/status":
            rec = _state.audio.is_recording if _state.audio else False
            self._send_json({"status": "ready", "model_loaded": _state.model_loaded, "recording": rec})
        elif self.path == "/settings":
            if _state.config:
                self._send_json(asdict(_state.config))
            else:
                self._send_error(500, "Config not loaded")
        else:
            self._send_error(404, "Not found")

    def do_POST(self) -> None:
        routes = {
            "/start_recording": self._start_recording,
            "/stop_recording": self._stop_recording,
            "/reformat": self._reformat,
            "/insert": self._insert,
            "/settings": self._save_settings,
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self._send_error(404, "Not found")

    def _start_recording(self) -> None:
        if _state.audio is None:
            self._send_error(503, "Audio not initialised")
            return
        _state.audio.start_recording()
        self._send_json({"status": "recording"})

    def _stop_recording(self) -> None:
        if _state.audio is None or _state.stt is None:
            self._send_error(503, "Audio/STT not initialised")
            return
        if not _state.audio.is_recording:
            self._send_error(409, "Not recording")
            return

        audio = _state.audio.stop_recording()
        sr = _state.config.audio.sample_rate if _state.config else 16000
        duration = len(audio) / sr

        if len(audio) == 0:
            self._send_json({"text": "", "raw": "", "duration": 0.0})
            return

        if not _state.model_loaded:
            self._send_error(503, "STT model not loaded yet")
            return

        result = _state.stt.transcribe(audio, sample_rate=sr)
        raw_text = result.text
        cleaned = raw_text

        if _state.llm and _state.llm.is_enabled and raw_text.strip():
            try:
                window = get_active_window()
                ctx = ProcessingContext(app_name=window.process_name, window_title=window.title)
                loop = asyncio.new_event_loop()
                try:
                    processed = loop.run_until_complete(_state.llm.cleanup(raw_text, ctx))
                    cleaned = processed.text
                finally:
                    loop.close()
            except Exception:
                logger.exception("LLM cleanup failed, returning raw transcript")

        self._send_json({"text": cleaned, "raw": raw_text, "duration": round(duration, 2)})

    def _reformat(self) -> None:
        body = self._read_json()
        if body is None:
            return
        text = body.get("text", "")
        fmt = body.get("format", "as_is")
        if not text:
            self._send_error(400, "Missing text")
            return
        if not _state.llm or not _state.llm.is_enabled:
            self._send_error(503, "LLM not enabled")
            return
        try:
            target = TextFormat(fmt)
        except ValueError:
            self._send_error(400, f"Unknown format: {fmt}")
            return

        window = get_active_window()
        ctx = ProcessingContext(app_name=window.process_name, window_title=window.title)
        loop = asyncio.new_event_loop()
        try:
            processed = loop.run_until_complete(_state.llm.reformat(text, target, ctx))
        except Exception:
            logger.exception("LLM reformat failed")
            self._send_error(500, "Reformat failed")
            return
        finally:
            loop.close()
        self._send_json({"text": processed.text})

    def _insert(self) -> None:
        body = self._read_json()
        if body is None:
            return
        text = body.get("text", "")
        if not text:
            self._send_error(400, "Missing text")
            return
        if _state.inserter is None:
            self._send_error(503, "Inserter not initialised")
            return
        ok = _state.inserter.insert_text(text)
        self._send_json({"status": "ok" if ok else "failed"})

    def _save_settings(self) -> None:
        body = self._read_json()
        if body is None:
            return
        lines = _dict_to_toml(body)
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        USER_CONFIG_PATH.write_text(lines, encoding="utf-8")
        _state.config = load_config()
        self._send_json({"status": "saved"})


def _dict_to_toml(data: dict, prefix: str = "") -> str:
    lines: list[str] = []
    tables: list[tuple[str, dict]] = []
    for k, v in data.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            tables.append((full, v))
        elif isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f"{k} = {v}")
    result = "\n".join(lines)
    for tk, td in tables:
        result += f"\n\n[{tk}]\n{_dict_to_toml(td, prefix=tk)}"
    return result


def _load_model_bg() -> None:
    _state.model_loading = True
    try:
        cfg = _state.config
        _state.stt.load_model(model_name=cfg.stt.model, device=cfg.stt.device, compute_type=cfg.stt.compute_type)
        _state.model_loaded = True
        logger.info("STT model loaded")
    except Exception:
        logger.exception("Failed to load STT model")
    finally:
        _state.model_loading = False


def _init_components() -> None:
    _state.config = load_config()
    cfg = _state.config
    _state.event_bus = EventBus()
    _state.audio = AudioCapture(config=cfg.audio, event_bus=_state.event_bus, max_recording_seconds=cfg.general.max_recording_seconds)
    try:
        _state.audio.initialize()
    except Exception:
        logger.exception("Audio init failed")
        _state.audio = None
    _state.stt = FasterWhisperEngine(beam_size=cfg.stt.beam_size)
    threading.Thread(target=_load_model_bg, daemon=True, name="stt-loader").start()
    if cfg.llm.enabled:
        try:
            _state.llm = LiteLLMProcessor(config=cfg)
        except Exception:
            logger.exception("LLM init failed")
    _state.inserter = TextInserter(config=cfg.insertion)
    logger.info("Components initialised")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stderr)
    logger.info("DictateMe server starting on %s:%d", HOST, PORT)
    _init_components()
    server = HTTPServer((HOST, PORT), DictateMeHandler)
    logger.info("Listening on http://%s:%d", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        server.server_close()
        if _state.audio:
            _state.audio.shutdown()
        if _state.stt:
            _state.stt.unload_model()


if __name__ == "__main__":
    main()
