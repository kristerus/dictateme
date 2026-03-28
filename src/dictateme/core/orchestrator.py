"""Core orchestrator: central state machine that coordinates all layers.

The orchestrator manages the dictation pipeline:
  IDLE -> RECORDING -> TRANSCRIBING -> LLM_PROCESSING ->
  FORMAT_SELECTION -> INSERTING -> IDLE

All inter-component communication flows through events. The orchestrator
subscribes to events and drives transitions.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import TYPE_CHECKING

from .events import Event, EventType
from .types import AppState, ProcessingContext, TextFormat

if TYPE_CHECKING:
    from ..audio.capture import AudioCapture
    from ..insertion.inserter import TextInserter
    from ..llm.processor import LLMProcessor
    from ..stt.faster_whisper import FasterWhisperEngine
    from ..ui.overlay import Overlay
    from ..ui.tray import SystemTray
    from .config import AppConfig
    from .event_bus import EventBus

logger = logging.getLogger(__name__)

# Map format key indices to TextFormat values
FORMAT_KEY_MAP: list[TextFormat] = [
    TextFormat.AS_IS,
    TextFormat.FORMAL,
    TextFormat.CASUAL,
    TextFormat.EMAIL,
    TextFormat.BULLET_POINTS,
    TextFormat.CODE_COMMENT,
    TextFormat.AI_PROMPT,
    TextFormat.SLACK_MESSAGE,
    TextFormat.CUSTOM,
]


class Orchestrator:
    """Central state machine coordinating all DictateMe components.

    Subscribes to events from the hotkey manager, audio capture, STT
    engine, and LLM processor. Drives the pipeline forward by emitting
    events and calling component methods.
    """

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        audio_capture: AudioCapture,
        stt_engine: FasterWhisperEngine,
        llm_processor: LLMProcessor,
        text_inserter: TextInserter,
        tray: SystemTray,
        overlay: Overlay,
    ) -> None:
        self._config = config
        self._bus = event_bus
        self._audio = audio_capture
        self._stt = stt_engine
        self._llm = llm_processor
        self._inserter = text_inserter
        self._tray = tray
        self._overlay = overlay

        self._state = AppState.IDLE
        self._current_text: str = ""
        self._window_context: ProcessingContext | None = None
        self._active_window = None

        # Processing happens on a background thread
        self._work_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self._processing_thread: threading.Thread | None = None
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_event = threading.Event()

        # Auto-insert timer ID (for tkinter after())
        self._auto_insert_timer: str | None = None

    def start(self) -> None:
        """Subscribe to events and start the processing thread."""
        self._bus.subscribe(EventType.HOTKEY_PRESSED, self._on_hotkey_pressed)
        self._bus.subscribe(EventType.HOTKEY_RELEASED, self._on_hotkey_released)
        self._bus.subscribe(EventType.CANCEL_PRESSED, self._on_cancel)
        self._bus.subscribe(EventType.FORMAT_KEY_PRESSED, self._on_format_key)

        # Start background processing thread
        self._processing_thread = threading.Thread(
            target=self._processing_loop, name="processing", daemon=True
        )
        self._processing_thread.start()

        self._set_state(AppState.IDLE)
        logger.info("Orchestrator started")

    def stop(self) -> None:
        """Shut down the orchestrator."""
        self._shutdown_event.set()
        self._work_queue.put(("shutdown", {}))
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)
        logger.info("Orchestrator stopped")

    def _set_state(self, new_state: AppState) -> None:
        """Transition to a new state."""
        old = self._state
        self._state = new_state
        logger.debug("State: %s -> %s", old.value, new_state.value)

        # Update UI
        state_to_tray = {
            AppState.IDLE: "idle",
            AppState.RECORDING: "recording",
            AppState.TRANSCRIBING: "processing",
            AppState.LLM_PROCESSING: "processing",
            AppState.FORMAT_SELECTION: "idle",
            AppState.INSERTING: "processing",
        }
        self._tray.set_state(state_to_tray.get(new_state, "idle"))

        self._bus.emit(Event(
            type=EventType.STATE_CHANGED,
            data={"old": old.value, "new": new_state.value},
        ))

    # ── Event handlers ──────────────────────────────────────────

    def _on_hotkey_pressed(self, event: Event) -> None:
        """Handle hotkey press — start recording."""
        if self._state != AppState.IDLE:
            logger.debug("Ignoring hotkey press in state %s", self._state.value)
            return

        # Snapshot the active window before we show our overlay
        self._active_window = self._inserter.get_active_window()
        self._window_context = ProcessingContext(
            app_name=self._active_window.process_name,
            window_title=self._active_window.title,
        )

        self._set_state(AppState.RECORDING)
        self._audio.start_recording()
        self._overlay.show_recording()
        self._bus.emit(Event(type=EventType.RECORDING_STARTED))

    def _on_hotkey_released(self, event: Event) -> None:
        """Handle hotkey release — stop recording and start processing."""
        if self._state != AppState.RECORDING:
            return

        audio = self._audio.stop_recording()
        self._bus.emit(Event(type=EventType.RECORDING_STOPPED))

        if len(audio) < 1600:  # Less than 0.1s of audio at 16kHz
            logger.info("Recording too short, discarding")
            self._overlay.hide()
            self._set_state(AppState.IDLE)
            return

        # Queue transcription work
        self._overlay.show_processing()
        self._set_state(AppState.TRANSCRIBING)
        self._work_queue.put(("transcribe", {"audio": audio}))

    def _on_cancel(self, event: Event) -> None:
        """Handle cancel key — abort current operation."""
        if self._state == AppState.RECORDING:
            self._audio.stop_recording()
        elif self._state == AppState.FORMAT_SELECTION:
            if self._auto_insert_timer:
                # Cancel auto-insert (would need tkinter root reference)
                pass

        self._overlay.hide()
        self._current_text = ""
        self._set_state(AppState.IDLE)
        logger.info("Operation cancelled")

    def _on_format_key(self, event: Event) -> None:
        """Handle format key press during format selection."""
        if self._state != AppState.FORMAT_SELECTION:
            return

        key_index = event.data.get("index", 0)
        if 0 <= key_index < len(FORMAT_KEY_MAP):
            target_format = FORMAT_KEY_MAP[key_index]
            if target_format == TextFormat.AS_IS:
                self._do_insert(self._current_text)
            else:
                self._set_state(AppState.LLM_PROCESSING)
                self._overlay.show_processing()
                self._work_queue.put((
                    "reformat",
                    {"text": self._current_text, "format": target_format},
                ))

    # ── Processing thread ────────────────────────────────────────

    def _processing_loop(self) -> None:
        """Background thread that handles STT and LLM work."""
        self._async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._async_loop)

        while not self._shutdown_event.is_set():
            try:
                task_type, data = self._work_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if task_type == "shutdown":
                break

            try:
                if task_type == "transcribe":
                    self._do_transcribe(data["audio"])
                elif task_type == "reformat":
                    self._do_reformat(data["text"], data["format"])
            except Exception:
                logger.exception("Error in processing loop")
                self._overlay.hide()
                self._set_state(AppState.IDLE)

        self._async_loop.close()

    def _do_transcribe(self, audio: object) -> None:
        """Run STT and optionally LLM cleanup."""
        import numpy as np

        self._bus.emit(Event(type=EventType.TRANSCRIPTION_STARTED))

        result = self._stt.transcribe(np.asarray(audio))

        if not result.text.strip():
            logger.info("Empty transcription, discarding")
            self._overlay.hide()
            self._set_state(AppState.IDLE)
            return

        self._bus.emit(Event(
            type=EventType.TRANSCRIPTION_COMPLETE,
            data={"text": result.text},
        ))

        raw_text = result.text

        # LLM cleanup
        if self._llm.is_enabled and self._window_context:
            self._set_state(AppState.LLM_PROCESSING)
            self._bus.emit(Event(type=EventType.LLM_PROCESSING_STARTED))

            processed = self._async_loop.run_until_complete(
                self._llm.cleanup(raw_text, self._window_context)
            )
            self._current_text = processed.text

            self._bus.emit(Event(
                type=EventType.LLM_PROCESSING_COMPLETE,
                data={"text": processed.text},
            ))
        else:
            self._current_text = raw_text
            self._bus.emit(Event(type=EventType.LLM_PROCESSING_SKIPPED))

        # Show preview and enter format selection
        auto_delay = self._config.formatting.auto_insert_delay_ms
        if auto_delay == 0:
            # Instant insert, no format selection
            self._do_insert(self._current_text)
        else:
            self._set_state(AppState.FORMAT_SELECTION)
            show_formats = self._config.formatting.show_preview
            self._overlay.show_text_preview(self._current_text, show_formats)

            # Schedule auto-insert after delay
            # (Using threading.Timer since we're not on the tkinter thread)
            timer = threading.Timer(
                auto_delay / 1000.0,
                self._auto_insert,
            )
            timer.daemon = True
            timer.start()

    def _do_reformat(self, text: str, target_format: TextFormat) -> None:
        """Run LLM reformat and insert."""
        if self._window_context is None:
            self._window_context = ProcessingContext(app_name="unknown", window_title="")

        processed = self._async_loop.run_until_complete(
            self._llm.reformat(text, target_format, self._window_context)
        )
        self._do_insert(processed.text)

    def _auto_insert(self) -> None:
        """Called by auto-insert timer — insert if still in FORMAT_SELECTION."""
        if self._state == AppState.FORMAT_SELECTION:
            self._do_insert(self._current_text)

    def _do_insert(self, text: str) -> None:
        """Final text insertion."""
        self._set_state(AppState.INSERTING)
        self._bus.emit(Event(type=EventType.TEXT_INSERTING, data={"text": text}))

        success = self._inserter.insert_text(text, self._active_window)

        if success:
            self._bus.emit(Event(type=EventType.TEXT_INSERTED, data={"text": text}))
        else:
            self._bus.emit(Event(type=EventType.TEXT_INSERTION_FAILED))
            logger.error("Text insertion failed")

        self._overlay.hide()
        self._current_text = ""
        self._set_state(AppState.IDLE)
