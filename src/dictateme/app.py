"""Application bootstrap: wires all components together and runs the main loop.

When pywebview is available, the main thread runs the webview event loop
(required by Windows). When falling back to tkinter, tkinter runs on the
main thread. All other components (tray, hotkeys, audio, STT, LLM) run
on background threads.
"""

from __future__ import annotations

import logging
import sys
import threading

from .audio.capture import AudioCapture
from .core.config import AppConfig, load_config
from .core.event_bus import EventBus
from .core.orchestrator import Orchestrator
from .hotkey.manager import HotkeyManager
from .insertion.inserter import TextInserter
from .llm.processor import LiteLLMProcessor
from .stt.faster_whisper import FasterWhisperEngine
from .ui.overlay import create_overlay, has_webview
from .ui.tray import SystemTray
from .utils.log import setup_logging
from .utils.platform import check_platform

logger = logging.getLogger(__name__)


class DictateApp:
    """Main application class. Owns all components and runs the event loop."""

    def __init__(self) -> None:
        self._config: AppConfig | None = None
        self._event_bus: EventBus | None = None
        self._orchestrator: Orchestrator | None = None
        self._hotkey_manager: HotkeyManager | None = None
        self._audio_capture: AudioCapture | None = None
        self._stt_engine: FasterWhisperEngine | None = None
        self._llm_processor: LiteLLMProcessor | None = None
        self._text_inserter: TextInserter | None = None
        self._tray: SystemTray | None = None
        self._overlay = None
        self._root = None
        self._use_webview = False

    def run(self) -> None:
        """Initialize all components and start the application."""
        self._config = load_config()
        setup_logging(self._config.general.log_level)
        check_platform()

        logger.info("DictateMe v0.1.0 starting...")

        self._use_webview = has_webview()

        # Create the event bus
        self._event_bus = EventBus()

        # Create components (no main-thread dependency)
        self._audio_capture = AudioCapture(
            config=self._config.audio,
            event_bus=self._event_bus,
            max_recording_seconds=self._config.general.max_recording_seconds,
        )
        self._stt_engine = FasterWhisperEngine(
            beam_size=self._config.stt.beam_size,
        )
        self._llm_processor = LiteLLMProcessor(config=self._config)
        self._text_inserter = TextInserter(config=self._config.insertion)
        self._tray = SystemTray(on_quit=self._shutdown)

        # Create overlay
        self._overlay = create_overlay(
            ui_config=self._config.ui,
            formatting_config=self._config.formatting,
        )

        if self._use_webview:
            self._run_with_webview()
        else:
            self._run_with_tkinter()

    def _run_with_webview(self) -> None:
        """Run with pywebview on the main thread."""
        # Create the webview window (must be before start)
        self._overlay.create_window()

        # Start all background components
        self._start_background_components()

        logger.info("DictateMe ready. Press %s to dictate.", self._config.hotkey.key_combo)

        # Webview main loop (blocks on main thread)
        try:
            self._overlay.start_main_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _run_with_tkinter(self) -> None:
        """Run with tkinter on the main thread (fallback)."""
        import tkinter as tk

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("DictateMe")

        self._overlay.initialize(self._root)

        # Start all background components
        self._start_background_components()

        logger.info("DictateMe ready. Press %s to dictate.", self._config.hotkey.key_combo)

        # Tkinter main loop (blocks on main thread)
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _start_background_components(self) -> None:
        """Start tray, hotkeys, orchestrator, and model loading."""
        # Orchestrator
        self._orchestrator = Orchestrator(
            config=self._config,
            event_bus=self._event_bus,
            audio_capture=self._audio_capture,
            stt_engine=self._stt_engine,
            llm_processor=self._llm_processor,
            text_inserter=self._text_inserter,
            tray=self._tray,
            overlay=self._overlay,
        )

        # Hotkey manager
        self._hotkey_manager = HotkeyManager(
            config=self._config.hotkey,
            event_bus=self._event_bus,
        )

        self._tray.start()
        self._orchestrator.start()
        self._hotkey_manager.start()

        # Load STT model in background
        threading.Thread(
            target=self._load_models,
            name="model-loader",
            daemon=True,
        ).start()

    def _load_models(self) -> None:
        """Load STT model in background thread."""
        try:
            self._stt_engine.load_model(
                model_name=self._config.stt.model,
                device=self._config.stt.device,
                compute_type=self._config.stt.compute_type,
            )
            self._audio_capture.initialize()
            self._tray.set_state("idle")
            logger.info("Models loaded, ready for dictation")
        except Exception:
            logger.exception("Failed to load models")
            self._tray.set_state("error")

    def _shutdown(self) -> None:
        """Gracefully shut down all components."""
        logger.info("Shutting down...")

        if self._hotkey_manager:
            self._hotkey_manager.stop()
        if self._orchestrator:
            self._orchestrator.stop()
        if self._audio_capture:
            self._audio_capture.shutdown()
        if self._stt_engine:
            self._stt_engine.unload_model()
        if self._tray:
            self._tray.stop()
        if self._root:
            self._root.quit()

        logger.info("Shutdown complete")
