# DictateMe - Architecture Document
## System-Wide Voice Dictation for Windows

**Version:** 0.1 (Architecture Draft)
**Date:** 2026-03-23
**Authors:** Architecture Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Component Architecture](#2-component-architecture)
3. [Tech Stack Decisions](#3-tech-stack-decisions)
4. [Data Flow](#4-data-flow)
5. [Module & File Structure](#5-module--file-structure)
6. [Key Interfaces & Protocols](#6-key-interfaces--protocols)
7. [Dependencies](#7-dependencies)
8. [Performance Considerations](#8-performance-considerations)
9. [Security & Privacy](#9-security--privacy)
10. [Feature Roadmap](#10-feature-roadmap)
11. [Open Questions & Risks](#11-open-questions--risks)

---

## 1. Executive Summary

DictateMe is an open-source, system-wide voice dictation tool for Windows that
captures speech, transcribes it locally, optionally refines it through an LLM,
and inserts the result into whatever application is focused. It aims to replicate
and improve upon Wispr Flow with full local-first privacy, support for both cloud
and local LLMs, and quick-reformat commands.

### Design Principles

- **Local-first**: Speech never leaves the machine unless the user explicitly
  configures a cloud LLM provider.
- **Fast**: Sub-2-second end-to-end latency for short utterances (target: <1s
  for transcription, <1s for LLM cleanup on local models).
- **Lightweight**: Idle memory < 80 MB. Active memory < 400 MB (excluding model
  weights loaded on demand).
- **Universal**: Works with any Windows application that accepts text input.
- **Simple to build and maintain**: Three-person team. Favor boring technology
  and clear module boundaries over clever abstractions.

---

## 2. Component Architecture

```
+------------------------------------------------------------------+
|                        DictateMe System                          |
+------------------------------------------------------------------+
|                                                                  |
|  +------------------+     +----------------------------------+   |
|  |   System Tray    |     |        Settings / Config         |   |
|  |   (pystray)      |<--->|        (TOML file)               |   |
|  +------------------+     +----------------------------------+   |
|         |                            |                           |
|         v                            v                           |
|  +------------------+     +----------------------------------+   |
|  | Global Hotkey    |     |     Overlay / Feedback UI        |   |
|  | Manager          |     |     (tkinter minimal popup)      |   |
|  | (keyboard lib)   |     +----------------------------------+   |
|  +------------------+                |                           |
|         |                            |                           |
|         v                            v                           |
|  +--------------------------------------------------+           |
|  |              Core Orchestrator                    |           |
|  |  (state machine: idle -> recording -> processing  |           |
|  |   -> formatting -> inserting -> idle)             |           |
|  +--------------------------------------------------+           |
|       |            |            |             |                  |
|       v            v            v             v                  |
|  +---------+ +-----------+ +----------+ +------------+          |
|  | Audio   | | STT       | | LLM      | | Text       |          |
|  | Capture | | Engine    | | Processor| | Inserter   |          |
|  | Layer   | | Layer     | | Layer    | | Layer      |          |
|  +---------+ +-----------+ +----------+ +------------+          |
|  |sounddev.| |faster-    | |litellm  | |clipboard + |          |
|  |silero   | |whisper    | |ollama   | |SendInput   |          |
|  |VAD      | |           | |openai   | |UIAutomation|          |
|  +---------+ +-----------+ +----------+ +------------+          |
|       |            |            |             |                  |
|       v            v            v             v                  |
|  +---------+ +-----------+ +----------+ +------------+          |
|  |Mic/WASAPI| |GPU/CPU   | |Local/   | |Win32 API   |          |
|  |PortAudio | |CUDA/CPU  | |Cloud API| |Accessibility|          |
|  +---------+ +-----------+ +----------+ +------------+          |
+------------------------------------------------------------------+
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **System Tray** | Always-running entry point. Shows status icon (idle / recording / processing). Menu for settings, quit, pause. |
| **Global Hotkey Manager** | Registers system-wide hotkeys. Communicates press/release events to Orchestrator. |
| **Overlay UI** | Minimal floating indicator during recording. Shows transcription preview. Displays format selection menu. |
| **Core Orchestrator** | Central state machine. Coordinates all layers. Manages the pipeline from recording to insertion. |
| **Audio Capture Layer** | Opens mic stream, buffers audio, runs VAD to detect speech start/end. Streams chunks to STT. |
| **STT Engine Layer** | Runs faster-whisper model. Accepts audio chunks, returns partial/final transcripts. |
| **LLM Processor Layer** | Takes raw transcript + context (app name, field type). Returns cleaned/formatted text. |
| **Text Inserter Layer** | Detects active window context. Inserts final text using the most reliable method for that application. |
| **Settings / Config** | Persists user preferences: hotkeys, LLM provider, model selection, formatting presets, audio device. |

---

## 3. Tech Stack Decisions

### 3.1 Language: Python 3.12+

**Rationale:**
- Richest ecosystem for audio, ML, and Windows system integration.
- faster-whisper, silero-vad, sounddevice, litellm, pystray, pywin32 all
  have first-class Python support.
- Team velocity matters more than squeezing an extra 10ms. The hot path
  (audio capture, STT inference) runs in C/C++/CUDA underneath anyway.
- Packaging via PyInstaller or Nuitka for single-exe distribution.

**Rejected alternatives:**
- *Rust (full)*: Whisper bindings immature. Win32 accessibility crate
  ecosystem thin. Would slow development significantly for marginal
  runtime gains on non-hot-path code.
- *Tauri + Python sidecar*: Adds IPC complexity (JSON over stdio/HTTP)
  between the Rust GUI shell and Python backend. For a system tray app
  with a minimal overlay, the GUI framework overhead is not justified.
  The Python tray/overlay approach is simpler and sufficient.
- *Electron*: 150+ MB memory overhead at idle. Antithetical to "lightweight."

**When to reconsider Tauri:** If the project grows to need a rich settings
UI, onboarding wizard, or visual audio waveform display, Tauri with a
Python sidecar (FastAPI over localhost) becomes worthwhile. This is
earmarked for v2.0.

### 3.2 Speech-to-Text: faster-whisper

**Rationale:**
- 4x faster than original Whisper with equivalent accuracy.
- Better CPU performance than whisper.cpp (14s vs 46s on small.en model
  in benchmarks).
- Native Python API -- no FFI/binding friction.
- Supports int8/float16 quantization for lower memory usage.
- Built-in VAD integration via silero-vad.
- CTranslate2 backend handles CUDA, cuDNN, and CPU optimally.

**Model selection strategy:**
- Default: `small.en` (good accuracy, fast, ~500 MB VRAM or pure CPU).
- Low-resource: `tiny.en` (fastest, acceptable accuracy for clean mic).
- High-accuracy: `medium.en` or `large-v3` (user opt-in, needs 2+ GB VRAM).
- Non-English: `small`, `medium`, `large-v3` (multilingual variants).

**Rejected alternatives:**
- *whisper.cpp*: Better VRAM efficiency but slower on CPU, less Pythonic
  API, fewer features (no built-in VAD, less quantization flexibility).
- *Cloud STT (Deepgram, AssemblyAI)*: Violates local-first principle.
  May be offered as optional provider in v1.0+.

### 3.3 Voice Activity Detection: silero-vad

**Rationale:**
- 87.7% TPR at 5% FPR (far better than WebRTC VAD's 50%).
- < 1ms per audio chunk on CPU. Negligible overhead.
- Trained on 6000+ languages. Works well with diverse accents.
- Already integrated as an option in faster-whisper.

### 3.4 Audio Capture: sounddevice

**Rationale:**
- Cross-platform (helps future macOS/Linux ports).
- Built on PortAudio -- mature, low-latency.
- Simple callback-based API for streaming audio.
- Supports device enumeration for mic selection.

**Configuration:**
- Sample rate: 16000 Hz (Whisper's native rate, avoids resampling).
- Channels: 1 (mono).
- Format: int16 (matches Whisper input).
- Buffer/block size: 480 samples (30ms chunks for VAD compatibility).

### 3.5 LLM Processing: litellm

**Rationale:**
- Single `completion()` call works with 100+ providers: OpenAI, Anthropic,
  Ollama (local), Azure, Google, Mistral, Groq, and more.
- User brings their own API key for cloud providers.
- For local: user runs Ollama separately; litellm calls it on localhost:11434.
- Consistent error handling mapped to OpenAI exception types.
- Streaming support for progressive text display.
- No vendor lock-in. User switches providers by changing one config line.

**Rejected alternatives:**
- *Direct provider SDKs*: Would need separate code paths for each provider.
  litellm abstracts this away.
- *LangChain*: Over-engineered for our use case (single prompt, no chains,
  no retrieval). Adds 50+ transitive dependencies.

### 3.6 Text Insertion: Hybrid Strategy

Three methods, chosen per-application for reliability:

| Method | How it works | Best for | Limitation |
|--------|-------------|----------|------------|
| **Clipboard + Ctrl+V** | Copy text to clipboard, simulate Ctrl+V | Most applications, large text | Overwrites user's clipboard (mitigated by save/restore) |
| **SendInput (Unicode)** | Send each character as a Unicode keypress via Win32 SendInput | Short text, applications that intercept Ctrl+V | Slow for long text, can fail if app filters injected input |
| **UI Automation** | Use Windows Accessibility API to set text field value directly | Modern apps (WPF, UWP, Electron) | Not all apps expose editable text patterns |

**Default strategy:**
1. Save current clipboard contents.
2. Copy formatted text to clipboard.
3. Simulate Ctrl+V via SendInput.
4. After a short delay (50ms), restore original clipboard.

This is the most universally reliable approach. SendInput character-by-character
is used as fallback for applications known to intercept paste (e.g., some
terminal emulators). UI Automation is used when available for richer integration
(e.g., appending to existing text without selecting all).

### 3.7 Global Hotkey: keyboard library

**Rationale:**
- Hooks global keyboard events at the OS level (low-level keyboard hook).
- Works regardless of which application has focus.
- Supports both "hold to talk" (key down/up events) and "toggle" modes.
- Pure Python, no compilation needed.
- Actively maintained.

**Alternative considered:** `pynput` -- similar capabilities but `keyboard`
has a simpler API for the hold-to-talk pattern where we need raw key_down
and key_up events.

### 3.8 System Tray: pystray

**Rationale:**
- De facto standard for Python system tray on Windows.
- Lightweight, no GUI framework dependency beyond Pillow for icons.
- Supports dynamic icon updates (idle/recording/processing states).
- Context menu for settings, quit, status display.

### 3.9 Overlay UI: tkinter (minimal)

**Rationale:**
- Ships with Python -- zero additional dependencies.
- Only needed for: recording indicator, live transcription preview,
  format selection popup.
- Overrideredirect(True) for borderless floating window.
- Topmost attribute for always-on-top behavior.
- Transparent background support on Windows.

**Scope:** This is NOT a full GUI application. The overlay is a small
floating widget that appears near the cursor or in a fixed screen position
during dictation. It disappears when dictation ends.

### 3.10 Configuration: TOML

**Rationale:**
- Human-readable, editable in any text editor.
- Python 3.11+ has `tomllib` in stdlib. `tomli-w` for writing.
- Simpler than YAML (no gotchas), richer than INI.

---

## 4. Data Flow

### 4.1 Primary Dictation Flow

```
User presses hotkey (e.g., Ctrl+Win or hold-to-talk)
        |
        v
[1] HOTKEY MANAGER detects key_down
    --> sends START_RECORDING to Orchestrator
        |
        v
[2] ORCHESTRATOR transitions: IDLE -> RECORDING
    --> tells Audio Capture to start streaming
    --> tells Overlay UI to show recording indicator
    --> snapshots active window info (title, process, cursor position)
        |
        v
[3] AUDIO CAPTURE opens mic stream (sounddevice, 16kHz mono)
    --> feeds 30ms chunks to silero-vad
    --> VAD detects speech onset, begins buffering audio
    --> audio chunks accumulate in a ring buffer
        |
        v
[4] User releases hotkey (or presses stop toggle)
    --> HOTKEY MANAGER sends STOP_RECORDING
    --> Audio Capture stops, flushes final buffer
        |
        v
[5] ORCHESTRATOR transitions: RECORDING -> TRANSCRIBING
    --> sends complete audio buffer to STT Engine
    --> Overlay shows "Processing..." indicator
        |
        v
[6] STT ENGINE (faster-whisper) runs inference
    --> model: small.en (configurable)
    --> returns: raw transcript text
    --> example: "um so I think we should uh update the readme
        with the new installation steps and also fix that typo
        in the contributing guide"
        |
        v
[7] ORCHESTRATOR transitions: TRANSCRIBING -> LLM_PROCESSING
    --> Checks if LLM processing is enabled (user preference)
    --> If disabled, skip to step [9]
    --> If enabled, sends to LLM Processor
        |
        v
[8] LLM PROCESSOR builds prompt:
    SYSTEM: "You are a dictation assistant. Clean up the
    transcribed speech. Remove filler words, fix grammar,
    add punctuation. Match the tone to the context.
    Active application: {app_name}. Return ONLY the
    cleaned text, no explanations."

    USER: "{raw_transcript}"

    --> calls litellm.completion() with configured provider
    --> returns: "I think we should update the README with the
        new installation steps and also fix that typo in the
        contributing guide."
        |
        v
[9] ORCHESTRATOR transitions: LLM_PROCESSING -> FORMAT_SELECTION
    --> Overlay shows the processed text + format options (1-9 keys)
    --> Default: auto-insert after 1.5s timeout (configurable)
    --> User can press a number key for quick reformat:
        1: As-is (default)
        2: Formal
        3: Casual
        4: Email
        5: Bullet points
        6: Code comment
        7: AI prompt
        8: Slack message
        9: Custom (user-defined)
        |
        v
[10] If reformat requested:
    --> LLM PROCESSOR gets a second call with format instruction
    --> "Rewrite the following as {format_type}: {text}"
    --> Returns reformatted text
        |
        v
[11] ORCHESTRATOR transitions: FORMAT_SELECTION -> INSERTING
     --> sends final text to Text Inserter
     --> Overlay disappears
        |
        v
[12] TEXT INSERTER:
     --> saves clipboard
     --> copies final text to clipboard
     --> focuses the previously-detected active window
     --> simulates Ctrl+V
     --> restores clipboard (after 50ms delay)
        |
        v
[13] ORCHESTRATOR transitions: INSERTING -> IDLE
     --> Ready for next dictation
```

### 4.2 Timing Budget (Target)

| Phase | Target Latency | Notes |
|-------|---------------|-------|
| Hotkey detection | < 5ms | OS-level hook, near instant |
| Audio capture start | < 20ms | Stream already hot (see 8.1) |
| VAD processing | < 1ms/chunk | silero-vad benchmark |
| STT inference (small.en, 5s audio) | 200-800ms | GPU: ~200ms, CPU: ~800ms |
| LLM processing (local, short text) | 300-1500ms | Depends on model/hardware |
| LLM processing (cloud, short text) | 200-600ms | Network dependent |
| Text insertion | < 50ms | Clipboard + paste |
| **Total (with LLM, GPU STT)** | **< 1.5s** | |
| **Total (with LLM, CPU STT)** | **< 3s** | |
| **Total (no LLM, GPU STT)** | **< 0.5s** | Bypass mode |

### 4.3 State Machine

```
                 hotkey_down
    +------+  ------------->  +-----------+
    | IDLE |                  | RECORDING |
    +------+  <-------------  +-----------+
        ^       hotkey_up /         |
        |       cancel              | audio_ready
        |                           v
        |                    +--------------+
        |                    | TRANSCRIBING |
        |                    +--------------+
        |                           |
        |                           | transcript_ready
        |                           v
        |                    +----------------+
        |    (LLM disabled)  | LLM_PROCESSING |
        |<-------------------+----------------+
        |                           |
        |                           | llm_done
        |                           v
        |                    +------------------+
        |    (auto-insert    | FORMAT_SELECTION |
        |     or key press)  +------------------+
        |                           |
        |                           | format_chosen
        |                           v
        |                    +-----------+
        +--------------------| INSERTING |
             insert_done     +-----------+
```

---

## 5. Module & File Structure

```
dictateme/
|
|-- pyproject.toml                 # Project metadata, dependencies
|-- config.default.toml            # Default configuration
|-- LICENSE                        # MIT or Apache-2.0
|
|-- src/
|   |-- dictateme/
|   |   |-- __init__.py
|   |   |-- __main__.py            # Entry point: python -m dictateme
|   |   |-- app.py                 # Application bootstrap, wiring
|   |   |
|   |   |-- core/
|   |   |   |-- __init__.py
|   |   |   |-- orchestrator.py    # Central state machine
|   |   |   |-- config.py          # Config loading/saving (TOML)
|   |   |   |-- events.py          # Event types (dataclasses/enums)
|   |   |   |-- event_bus.py       # Simple pub/sub event dispatcher
|   |   |   |-- types.py           # Shared type definitions
|   |   |
|   |   |-- audio/
|   |   |   |-- __init__.py
|   |   |   |-- capture.py         # Mic stream management (sounddevice)
|   |   |   |-- vad.py             # Voice activity detection (silero-vad)
|   |   |   |-- buffer.py          # Audio ring buffer
|   |   |   |-- devices.py         # Audio device enumeration
|   |   |
|   |   |-- stt/
|   |   |   |-- __init__.py
|   |   |   |-- engine.py          # STT engine interface (Protocol)
|   |   |   |-- faster_whisper.py  # faster-whisper implementation
|   |   |   |-- model_manager.py   # Model download, caching, selection
|   |   |
|   |   |-- llm/
|   |   |   |-- __init__.py
|   |   |   |-- processor.py       # LLM processing interface
|   |   |   |-- prompts.py         # System prompts, format templates
|   |   |   |-- providers.py       # Provider config (litellm wrapper)
|   |   |
|   |   |-- insertion/
|   |   |   |-- __init__.py
|   |   |   |-- inserter.py        # Text insertion coordinator
|   |   |   |-- clipboard.py       # Clipboard save/restore/paste
|   |   |   |-- sendinput.py       # Win32 SendInput wrapper
|   |   |   |-- ui_automation.py   # Windows UI Automation fallback
|   |   |   |-- context.py         # Active window detection
|   |   |
|   |   |-- hotkey/
|   |   |   |-- __init__.py
|   |   |   |-- manager.py         # Global hotkey registration
|   |   |   |-- bindings.py        # Key combo definitions
|   |   |
|   |   |-- ui/
|   |   |   |-- __init__.py
|   |   |   |-- tray.py            # System tray icon (pystray)
|   |   |   |-- overlay.py         # Recording/processing overlay
|   |   |   |-- icons.py           # Icon generation/loading
|   |   |
|   |   |-- utils/
|   |       |-- __init__.py
|   |       |-- logging.py         # Structured logging setup
|   |       |-- threading.py       # Thread helpers, cancellation
|   |       |-- platform.py        # Windows version detection
|   |
|-- tests/
|   |-- conftest.py
|   |-- test_orchestrator.py
|   |-- test_audio_capture.py
|   |-- test_vad.py
|   |-- test_stt_engine.py
|   |-- test_llm_processor.py
|   |-- test_inserter.py
|   |-- test_hotkey.py
|   |-- test_config.py
|   |-- fixtures/                   # Test audio samples
|       |-- short_speech.wav
|       |-- noisy_speech.wav
|
|-- assets/
|   |-- icon_idle.png
|   |-- icon_recording.png
|   |-- icon_processing.png
|
|-- scripts/
    |-- build.py                    # PyInstaller build script
    |-- download_models.py          # Pre-download Whisper models
```

### Module Dependency Graph (imports flow downward)

```
    app.py
      |
      v
  orchestrator.py
      |
      +------+--------+--------+--------+
      |      |        |        |        |
      v      v        v        v        v
   audio/  stt/     llm/   insertion/ hotkey/
      |      |        |        |        |
      v      v        v        v        v
   core/events.py, core/types.py, core/config.py
```

**Rule:** No lateral imports between feature modules (audio, stt, llm,
insertion, hotkey). All communication goes through the Orchestrator via
the event bus. This keeps modules independently testable and replaceable.

---

## 6. Key Interfaces & Protocols

### 6.1 STT Engine Protocol

```python
from typing import Protocol
from dataclasses import dataclass
import numpy as np


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float
    duration_seconds: float
    segments: list["TranscriptionSegment"]


@dataclass
class TranscriptionSegment:
    start: float  # seconds
    end: float    # seconds
    text: str
    confidence: float


class STTEngine(Protocol):
    """Protocol for speech-to-text engines.

    Implementations must be thread-safe. The engine is initialized once
    and called from the orchestrator's processing thread.
    """

    def load_model(self, model_name: str, device: str = "auto") -> None:
        """Load a model. Blocks until ready. Call once at startup."""
        ...

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe a complete audio buffer.

        Args:
            audio: float32 numpy array, mono, normalized to [-1.0, 1.0]
            sample_rate: Sample rate in Hz (default 16000)

        Returns:
            TranscriptionResult with full text and segments.
        """
        ...

    def unload_model(self) -> None:
        """Free model resources."""
        ...
```

### 6.2 LLM Processor Interface

```python
from typing import Protocol
from dataclasses import dataclass
from enum import Enum


class TextFormat(Enum):
    AS_IS = "as_is"
    FORMAL = "formal"
    CASUAL = "casual"
    EMAIL = "email"
    BULLET_POINTS = "bullet_points"
    CODE_COMMENT = "code_comment"
    AI_PROMPT = "ai_prompt"
    SLACK_MESSAGE = "slack_message"
    CUSTOM = "custom"


@dataclass
class ProcessingContext:
    app_name: str          # e.g. "Code", "chrome", "OUTLOOK.EXE"
    window_title: str      # e.g. "architecture.md - DictateMe - Visual Studio Code"
    field_hint: str | None # e.g. "email_body", "search_bar", inferred from context


@dataclass
class ProcessedText:
    text: str
    format_applied: TextFormat
    model_used: str
    latency_ms: float


class LLMProcessor(Protocol):
    """Protocol for LLM text processing."""

    async def cleanup(
        self,
        raw_transcript: str,
        context: ProcessingContext,
    ) -> ProcessedText:
        """Clean up raw transcription: remove fillers, fix grammar, punctuate."""
        ...

    async def reformat(
        self,
        text: str,
        target_format: TextFormat,
        context: ProcessingContext,
        custom_instruction: str | None = None,
    ) -> ProcessedText:
        """Reformat already-cleaned text into a specific style."""
        ...
```

### 6.3 Text Inserter Interface

```python
from typing import Protocol
from dataclasses import dataclass
from enum import Enum


class InsertionMethod(Enum):
    CLIPBOARD_PASTE = "clipboard_paste"
    SEND_INPUT_UNICODE = "sendinput_unicode"
    UI_AUTOMATION = "ui_automation"


@dataclass
class ActiveWindowInfo:
    hwnd: int              # Window handle
    title: str
    process_name: str
    process_id: int
    is_elevated: bool      # Running as admin?


class TextInserter(Protocol):
    """Protocol for inserting text into the active application."""

    def get_active_window(self) -> ActiveWindowInfo:
        """Snapshot the currently focused window."""
        ...

    def insert_text(
        self,
        text: str,
        window: ActiveWindowInfo,
        method: InsertionMethod = InsertionMethod.CLIPBOARD_PASTE,
    ) -> bool:
        """Insert text into the target window. Returns True on success."""
        ...
```

### 6.4 Event Types

```python
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import numpy as np


class EventType(Enum):
    # Hotkey events
    HOTKEY_PRESSED = auto()
    HOTKEY_RELEASED = auto()
    FORMAT_KEY_PRESSED = auto()

    # Audio events
    RECORDING_STARTED = auto()
    RECORDING_STOPPED = auto()
    AUDIO_READY = auto()
    VAD_SPEECH_START = auto()
    VAD_SPEECH_END = auto()

    # STT events
    TRANSCRIPTION_STARTED = auto()
    TRANSCRIPTION_COMPLETE = auto()
    TRANSCRIPTION_PARTIAL = auto()  # For future streaming mode

    # LLM events
    LLM_PROCESSING_STARTED = auto()
    LLM_PROCESSING_COMPLETE = auto()
    LLM_PROCESSING_SKIPPED = auto()

    # Insertion events
    TEXT_INSERTING = auto()
    TEXT_INSERTED = auto()
    TEXT_INSERTION_FAILED = auto()

    # System events
    ERROR = auto()
    STATE_CHANGED = auto()


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0  # Set by event bus
```

### 6.5 Configuration Schema

```toml
# config.default.toml

[general]
language = "en"
start_minimized = true
auto_start_with_windows = false
log_level = "INFO"

[hotkey]
mode = "hold"              # "hold" (push-to-talk) or "toggle"
key_combo = "ctrl+win"     # Modifier+key combination
cancel_key = "escape"

[audio]
device = "default"         # or specific device name/index
sample_rate = 16000
vad_threshold = 0.5        # silero-vad confidence threshold
silence_duration_ms = 500  # How long silence before auto-stop (toggle mode)

[stt]
engine = "faster-whisper"
model = "small.en"         # tiny.en | small.en | medium.en | large-v3
device = "auto"            # "auto" | "cuda" | "cpu"
compute_type = "float16"   # float16 | int8 | float32

[llm]
enabled = true
provider = "ollama"        # ollama | openai | anthropic | groq | azure | custom
model = "llama3.2:3b"     # Provider-specific model name

[llm.ollama]
base_url = "http://localhost:11434"

[llm.openai]
api_key = ""               # User provides their own key
model = "gpt-4o-mini"

[llm.anthropic]
api_key = ""
model = "claude-sonnet-4-20250514"

[llm.custom]
api_base = ""              # OpenAI-compatible endpoint
api_key = ""
model = ""

[formatting]
auto_insert_delay_ms = 1500   # 0 = instant insert, no format selection
show_preview = true
default_format = "as_is"

[formatting.presets]
# Customizable format presets
formal = "Rewrite in a formal, professional tone."
casual = "Rewrite in a casual, friendly tone."
email = "Format as a professional email body."
bullet_points = "Convert into concise bullet points."
code_comment = "Rewrite as a clear code comment (use // prefix for each line)."
ai_prompt = "Rewrite as a clear, detailed AI prompt."
slack_message = "Rewrite as a concise Slack message."

[insertion]
method = "clipboard_paste"   # clipboard_paste | sendinput | auto
restore_clipboard = true
clipboard_restore_delay_ms = 100

[ui]
overlay_position = "cursor"  # "cursor" | "center" | "top_right"
overlay_opacity = 0.9
show_recording_indicator = true
```

---

## 7. Dependencies

### 7.1 Core Dependencies

| Package | Version | Purpose | Size Impact |
|---------|---------|---------|-------------|
| `faster-whisper` | >= 1.1.0 | STT engine (CTranslate2 backend) | ~150 MB (+ model files) |
| `silero-vad` | >= 5.1 | Voice activity detection | ~2 MB (uses torch) |
| `sounddevice` | >= 0.5 | Audio capture | ~1 MB (PortAudio bundled) |
| `numpy` | >= 1.26 | Audio array operations | ~30 MB |
| `torch` | >= 2.2 | silero-vad runtime, CUDA for STT | ~800 MB (CPU) / ~2 GB (CUDA) |
| `litellm` | >= 1.50 | Unified LLM API | ~5 MB |
| `keyboard` | >= 0.13 | Global hotkeys | < 1 MB |
| `pystray` | >= 0.19 | System tray icon | < 1 MB |
| `Pillow` | >= 10.0 | Icon image handling (pystray dep) | ~10 MB |
| `pywin32` | >= 306 | Win32 API (clipboard, SendInput, process info) | ~30 MB |
| `psutil` | >= 5.9 | Process information | ~5 MB |

### 7.2 The PyTorch Problem

PyTorch is the heaviest dependency (~800 MB CPU, ~2 GB with CUDA). It is
needed by silero-vad. Mitigation strategies:

1. **For MVP**: Accept the torch dependency. Users who want GPU STT already
   have CUDA torch installed.
2. **For v1.0**: Investigate `silero-vad` ONNX runtime alternative (uses
   onnxruntime instead of torch, ~50 MB). The silero-vad repo provides
   ONNX models.
3. **For v1.0**: Consider CTranslate2's built-in VAD support to eliminate
   the separate silero-vad dependency entirely.

### 7.3 Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing |
| `pytest-asyncio` | Async test support |
| `ruff` | Linting and formatting |
| `mypy` | Type checking |
| `pyinstaller` | Binary packaging |
| `pre-commit` | Git hooks |

---

## 8. Performance Considerations

### 8.1 Model Pre-loading

The biggest latency hit is model loading. Strategies:

- **Eager load at startup**: Load the faster-whisper model when the app
  starts. Adds 2-5s to startup but ensures instant transcription.
- **Keep-alive**: Never unload the model while the app is running.
- **Warm mic stream**: Keep the sounddevice stream open but paused.
  Starting a paused stream is < 5ms vs. opening a new one (~50-100ms).

### 8.2 Audio Pipeline Optimization

```
Mic -> [30ms chunks] -> VAD -> [speech chunks buffer] -> STT
                         |
                    (non-speech: discard)
```

- Use a pre-allocated ring buffer (numpy array) to avoid allocation.
- VAD runs on every 30ms chunk (~533 calls/second for 16kHz audio).
  At < 1ms per call, this is negligible.
- Only the speech portion is sent to STT, reducing inference time.

### 8.3 Async LLM Calls

- Use `asyncio` for LLM calls to avoid blocking the main thread.
- litellm supports async via `acompletion()`.
- Enable streaming for real-time text preview in the overlay.

### 8.4 Thread Architecture

```
Main Thread (tkinter event loop for overlay)
  |
  +-- pystray thread (system tray, runs its own event loop)
  |
  +-- keyboard hook thread (global hotkeys, managed by keyboard lib)
  |
  +-- audio capture thread (sounddevice callback, real-time priority)
  |
  +-- processing thread (STT + LLM, compute-bound)
       Uses queue.Queue for work items from orchestrator
```

**Key constraint:** tkinter must run on the main thread on Windows.
All other work happens on dedicated threads. Communication uses
`threading.Event`, `queue.Queue`, and tkinter's `after()` for
thread-safe UI updates.

### 8.5 Memory Budget

| Component | Idle | Active |
|-----------|------|--------|
| Python runtime | 30 MB | 30 MB |
| faster-whisper model (small.en) | 250 MB | 350 MB |
| silero-vad model | 10 MB | 10 MB |
| Audio buffer (60s max) | 0 MB | ~2 MB |
| pystray + overlay | 15 MB | 20 MB |
| **Total** | **~305 MB** | **~412 MB** |

Note: These figures exclude PyTorch runtime overhead (~200-400 MB).
With ONNX-based VAD (v1.0 goal), idle drops to ~120 MB.

### 8.6 Startup Time Optimization

1. Lazy imports: Only import heavy modules (faster_whisper, torch) when
   first needed.
2. Show system tray icon immediately, load models in background thread.
3. Visual feedback: tray icon shows "loading" state until models are ready.
4. First dictation attempt before model is loaded queues the request and
   shows "Model loading, please wait..." in overlay.

---

## 9. Security & Privacy

### 9.1 Local-First Design

- Audio is processed locally by default. No audio data leaves the machine.
- When using local LLMs (Ollama), all text processing is also local.
- Cloud LLM usage requires explicit user configuration and API key entry.

### 9.2 API Key Storage

- API keys stored in user-local config file with OS-restricted permissions.
- Future: Use Windows Credential Manager (via `keyring` library) for
  encrypted key storage.
- Keys are never logged or included in error reports.

### 9.3 Clipboard Handling

- Clipboard contents are saved before insertion and restored after.
- If save/restore fails, log a warning but do not crash.
- Sensitive clipboard content (passwords from password managers) is a
  risk -- document this behavior clearly for users.

### 9.4 Privilege Level

- DictateMe runs at normal user privilege.
- Cannot inject text into elevated (admin) windows due to UIPI.
- Document this limitation. Do NOT ask users to run as admin.

---

## 10. Feature Roadmap

### Phase 0: Foundation (Weeks 1-2)

Goal: Skeleton that proves the pipeline works end-to-end.

- [ ] Project setup: pyproject.toml, ruff, mypy, basic CI
- [ ] Config loading from TOML
- [ ] System tray icon with quit menu
- [ ] Global hotkey (Ctrl+Win hold-to-talk)
- [ ] Mic capture with sounddevice (record to WAV for testing)
- [ ] faster-whisper transcription of WAV file
- [ ] Clipboard-based text insertion into active window
- [ ] Wire them together: hold key -> record -> transcribe -> insert
- [ ] Basic logging

### Phase 1: MVP (Weeks 3-5) -- v0.1.0

Goal: Usable daily driver for the development team.

- [ ] silero-vad integration (trim silence, auto-detect speech boundaries)
- [ ] Orchestrator state machine with proper transitions
- [ ] Event bus for component communication
- [ ] LLM cleanup (Ollama local by default)
- [ ] LLM provider switching (OpenAI, Anthropic via litellm)
- [ ] Overlay UI: recording indicator + live transcript preview
- [ ] Audio device selection in config
- [ ] Model selection in config
- [ ] Error handling and user-facing error messages
- [ ] Basic format selection (as-is, formal, casual)

### Phase 2: Polish (Weeks 6-8) -- v0.5.0

Goal: Ready for early adopters / public beta.

- [ ] Full format preset system (all 8 presets + custom)
- [ ] Settings UI (simple tkinter dialog or web-based localhost page)
- [ ] Hotkey customization
- [ ] Hold-to-talk AND toggle mode support
- [ ] Clipboard save/restore
- [ ] SendInput fallback for terminal apps
- [ ] Auto-start with Windows (registry entry)
- [ ] PyInstaller packaging (single .exe)
- [ ] Model auto-download on first run
- [ ] Update checker (GitHub releases API)

### Phase 3: v1.0.0 (Weeks 9-14)

Goal: Production-quality open-source release.

- [ ] ONNX-based VAD (drop PyTorch dependency)
- [ ] Streaming transcription (show words as they are recognized)
- [ ] UI Automation text insertion for modern apps
- [ ] Application-specific profiles (different formats per app)
- [ ] History: log recent dictations for re-insertion
- [ ] Inline correction: "replace X with Y" voice commands
- [ ] Multilingual support (auto-detect language)
- [ ] Proper installer (NSIS or WiX)
- [ ] Comprehensive test suite (>80% coverage on core modules)
- [ ] Documentation site

### Phase 4: v2.0.0 (Future)

Goal: Rich experience, cross-platform beginnings.

- [ ] Tauri-based settings UI and overlay (richer visuals)
- [ ] macOS support (CoreAudio, Accessibility API)
- [ ] Linux support (PipeWire, AT-SPI2)
- [ ] Plugin system for custom text transformations
- [ ] Voice profiles (adapt to user's speech patterns)
- [ ] Continuous dictation mode (always-on with wake word)
- [ ] Cloud sync for settings and profiles
- [ ] Team/enterprise features (shared prompts, compliance logging)
- [ ] Context-aware insertion (reads surrounding text for better LLM output)

---

## 11. Open Questions & Risks

### 11.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| PyTorch bloats the binary to >1 GB | Reduces adoption | ONNX VAD in v1.0; investigate torch-cpu minimal build |
| Clipboard restore race condition | User loses clipboard content | Add configurable delay; warn in docs; offer undo |
| Some apps block SendInput/paste | Text insertion fails silently | Maintain app-specific override list; UI Automation fallback |
| CUDA version conflicts with user's setup | STT fails on GPU | Default to CPU; test common CUDA versions; clear error messages |
| Global hotkey conflicts with existing apps | Hotkey does not register | Allow full customization; detect conflicts at registration time |
| Model download is 200-500 MB on first run | Bad first experience | Show progress bar; offer "lite" mode with tiny.en |

### 11.2 Open Design Questions

1. **Streaming vs. batch transcription?** Batch is simpler and more
   accurate. Streaming gives better UX (live preview). Start with batch
   for MVP, add streaming in v1.0.

2. **How to handle very long dictations (>60s)?** Options: chunk into
   30s segments and transcribe sequentially, or increase buffer limit.
   For MVP, cap at 60s and warn the user.

3. **Should the LLM see application context?** Sending the app name and
   window title improves formatting (e.g., code style in VS Code, email
   tone in Outlook) but raises privacy questions if using cloud LLM.
   Default: send context to local LLMs only, strip for cloud.

4. **Audio processing: push-to-talk only, or also auto-detect?** PTT
   is simpler and more predictable. Auto-detect (always-on mic with VAD)
   is more convenient but uses more CPU and raises privacy concerns.
   Start with PTT only.

5. **How to handle multi-monitor cursor positioning for overlay?** Use
   the cursor's current monitor. tkinter `winfo_pointerx/y` handles this.

---

## Appendix A: Comparison with Wispr Flow

| Feature | Wispr Flow | DictateMe (v1.0 target) |
|---------|-----------|------------------------|
| STT | Cloud (OpenAI/Meta servers) | Local (faster-whisper) |
| LLM cleanup | Cloud only | Local + Cloud (user choice) |
| Privacy | Audio sent to cloud | Local-first, never by default |
| Price | $10-20/month | Free (open source) |
| Platforms | Mac, Windows, iOS | Windows (Mac in v2.0) |
| Offline | No | Yes (fully local mode) |
| Custom formats | Limited | Fully customizable presets |
| Open source | No | Yes |
| Latency | 1-2 seconds | Target < 1.5s (GPU), < 3s (CPU) |
| Whisper mode | Yes (silent dictation) | Future (v2.0) |

## Appendix B: LLM Prompt Templates

### Cleanup Prompt (System)

```
You are a dictation assistant. Your job is to clean up speech-to-text
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
Window title: {window_title}
```

### Reformat Prompt (System)

```
Rewrite the following text in the specified format. Return ONLY the
reformatted text. No explanations, no quotation marks, no preamble.

Target format: {format_name}
Format instructions: {format_instructions}
```

---

*End of Architecture Document*
