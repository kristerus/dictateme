<p align="center">
  <img src="app/src-tauri/icons/128x128.png" alt="DictateMe" width="80" height="80">
</p>

<h1 align="center">DictateMe</h1>

<p align="center">
  <strong>Open-source voice dictation that runs entirely on your machine.</strong><br>
  Speak naturally in 99 languages. Text appears wherever your cursor is.<br>
  No cloud. No subscription. No data leaves your PC.
</p>

<p align="center">
  <a href="https://github.com/kristerus/dictateme/releases/latest"><img src="https://img.shields.io/github/v/release/kristerus/dictateme?color=%23FFBA08&label=download&style=flat-square" alt="Download"></a>
  <a href="https://github.com/kristerus/dictateme/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT License"></a>
  <a href="https://github.com/kristerus/dictateme/stargazers"><img src="https://img.shields.io/github/stars/kristerus/dictateme?style=flat-square&color=%23FFBA08" alt="Stars"></a>
  <a href="https://github.com/kristerus/dictateme/releases"><img src="https://img.shields.io/github/downloads/kristerus/dictateme/total?style=flat-square&color=%232DD4BF" alt="Downloads"></a>
  <a href="https://github.com/kristerus/dictateme/actions"><img src="https://img.shields.io/github/actions/workflow/status/kristerus/dictateme/release.yml?style=flat-square&label=build" alt="Build"></a>
</p>

<p align="center">
  <a href="#download">Download</a> &middot;
  <a href="#features">Features</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#llm-setup">LLM Setup</a> &middot;
  <a href="https://github.com/kristerus/dictateme/issues">Report Bug</a>
</p>

---

## Why DictateMe?

Most voice dictation tools send your audio to the cloud and charge monthly fees. DictateMe is different:

|  | Wispr Flow | DictateMe |
|---|---|---|
| **Price** | $10-20/month | **Free forever** |
| **Speech engine** | Cloud (their servers) | **Local (faster-whisper)** |
| **Works offline** | No | **Yes, fully offline** |
| **Audio privacy** | Sent to cloud | **Never leaves your PC** |
| **Languages** | ~30 | **99 with auto-detect** |
| **LLM cleanup** | Proprietary | **Ollama, OpenAI, Anthropic, Groq, any** |
| **Reformatting** | Limited | **8 presets, keyboard shortcuts** |
| **Open source** | No | **MIT License** |
| **Platforms** | Mac, Windows, iOS | **Windows, macOS, Linux** |

## Features

- **99 languages** with automatic detection - speak in English, German, Japanese, Spanish, Albanian, or [any Whisper language](https://github.com/openai/whisper#available-models-and-languages)
- **Local Whisper STT** powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with CTranslate2 - 4x faster than OpenAI's implementation
- **LLM text cleanup** removes filler words ("um", "uh", "like"), fixes grammar, adds punctuation - works with [Ollama](https://ollama.com) (local), OpenAI, Anthropic, Groq, or any provider
- **Instant reformatting** - dictate once, press `1-8` to reshape as formal text, email, Slack message, bullet points, code comments, or AI prompt
- **System-wide** - inserts text into any application: VS Code, Chrome, Outlook, Slack, terminals, anywhere you type
- **Keyboard-first** - `Ctrl+Shift+D` to record, number keys for formats, `Enter` to insert, `Esc` to cancel
- **Native desktop app** built with [Tauri](https://tauri.app) - dashboard, settings UI, system tray, floating overlay
- **GPU + CPU** - CUDA acceleration when available, fast int8 quantized CPU fallback
- **Privacy first** - audio is processed locally, never uploaded, never stored

## Download

<table>
<tr>
<td align="center"><strong>Windows</strong></td>
<td align="center"><strong>macOS</strong></td>
<td align="center"><strong>Linux</strong></td>
</tr>
<tr>
<td align="center"><a href="https://github.com/kristerus/dictateme/releases/latest/download/DictateMe_0.1.0_x64-setup.exe">Download .exe</a></td>
<td align="center"><a href="https://github.com/kristerus/dictateme/releases/latest/download/DictateMe_0.1.0_aarch64.dmg">Apple Silicon .dmg</a><br><a href="https://github.com/kristerus/dictateme/releases/latest/download/DictateMe_0.1.0_x64.dmg">Intel .dmg</a></td>
<td align="center"><a href="https://github.com/kristerus/dictateme/releases/latest/download/DictateMe_0.1.0_amd64.deb">.deb</a> · <a href="https://github.com/kristerus/dictateme/releases/latest/download/DictateMe_0.1.0_amd64.AppImage">.AppImage</a></td>
</tr>
</table>

Or [build from source](#quick-start) below.

## How It Works

```
Press Ctrl+Shift+D  →  Speak naturally  →  Text appears at your cursor
```

1. **Speak** - Press `Ctrl+Shift+D`, talk naturally in any language
2. **Pick a format** - Press `1-8` to reformat, or let it auto-insert after 1.5 seconds
3. **Done** - Text is inserted wherever your cursor was. Press `Enter` to insert immediately, `Esc` to cancel

### Format Shortcuts

| Key | Format | Example |
|-----|--------|---------|
| `1` | As-is | Clean transcript |
| `2` | Formal | Professional tone |
| `3` | Casual | Friendly, relaxed |
| `4` | Email | With greeting and closing |
| `5` | Bullets | Concise bullet list |
| `6` | Code | `// comment` style |
| `7` | AI Prompt | Clear instructions for AI |
| `8` | Slack | Brief and direct |

## Quick Start

### From Installer

Download from the [table above](#download), install, launch DictateMe, and press `Ctrl+Shift+D`.

### From Source

```bash
git clone https://github.com/kristerus/dictateme.git
cd dictateme

# Install Python backend
pip install -e ".[cpu]"       # CPU mode
# pip install -e ".[cuda]"   # or with NVIDIA GPU support

# Start the backend
python -m dictateme.server

# In another terminal, build and run the desktop app
cd app/src-tauri
cargo run
```

**Requirements:** Python 3.12+, Rust toolchain, microphone, ~500MB disk for the speech model.

## Configuration

Configure via the Settings UI in the app, or edit `~/.dictateme/config.toml`:

```toml
[general]
language = "auto"            # "auto" to detect, or "en", "de", "ja", "sq", etc.

[stt]
model = "base"               # tiny | base | small | medium | large-v3
device = "auto"              # auto | cuda | cpu
compute_type = "int8"        # int8 (fast CPU) | float16 (GPU) | float32
beam_size = 1                # 1 = fast, 5 = accurate

[llm]
enabled = false              # enable LLM cleanup and reformatting
provider = "ollama"          # ollama | openai | anthropic | groq | custom

[llm.ollama]
model = "llama3.2:3b"

[formatting]
auto_insert_delay_ms = 1500  # ms before auto-insert (0 = instant)
```

See [`config.default.toml`](config.default.toml) for all options.

## LLM Setup

DictateMe works great without an LLM - you get accurate Whisper transcription out of the box. Enable LLM for filler word removal and reformatting:

### Option 1: Local with Ollama (fully offline)

```bash
# Install from https://ollama.com
ollama pull llama3.2:3b
```

Set `llm.enabled = true` and `llm.provider = "ollama"` in Settings. No API key needed, fully private.

### Option 2: Cloud providers

Add your API key in the Settings UI. Supports:
- **OpenAI** - GPT-4o-mini (fast, cheap)
- **Anthropic** - Claude (high quality)
- **Groq** - Llama (very fast, free tier)
- **Custom** - any OpenAI-compatible endpoint

### Option 3: No LLM

Leave `llm.enabled = false`. Raw Whisper transcription is already good for most use cases.

## Architecture

```
┌──────────────────────────────────┐
│  Tauri Desktop App (Rust)        │
│  ├── Dashboard + Settings UI     │
│  ├── Floating dictation overlay  │
│  ├── System tray                 │
│  └── Global hotkey (Ctrl+Shift+D)│
└──────────┬───────────────────────┘
           │ HTTP (localhost:18234)
┌──────────┴───────────────────────┐
│  Python Sidecar Server           │
│  ├── Audio Capture (sounddevice) │
│  ├── VAD (silero-vad)            │
│  ├── STT (faster-whisper)        │
│  ├── LLM Cleanup (direct API)   │
│  └── Text Insertion (clipboard)  │
└──────────────────────────────────┘
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design document.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v           # run tests
ruff check src/            # lint
mypy src/                  # type check
```

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create your branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## Star History

If DictateMe is useful to you, consider giving it a star - it helps others discover the project.

## License

[MIT](LICENSE) - use it however you want.

---

<p align="center">
  Built with <a href="https://github.com/SYSTRAN/faster-whisper">faster-whisper</a> and <a href="https://tauri.app">Tauri</a>.
</p>
