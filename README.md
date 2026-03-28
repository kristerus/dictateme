# DictateMe

**System-wide voice dictation. Local-first. Free. Open source.**

Press **Ctrl+Shift+D**, speak naturally, press again — text appears wherever your cursor is. 99 languages. Runs entirely on your machine.

[Download](#download) · [Report Bug](https://github.com/kristerus/dictateme/issues)

---

## Why DictateMe?

|  | **Wispr Flow** | **DictateMe** |
|---|---|---|
| Price | $10–20/month | **Free forever** |
| Speech-to-text | Cloud (their servers) | **Local (your machine)** |
| Works offline | No | **Yes** |
| Audio privacy | Sent to cloud | **Never leaves your PC** |
| Languages | ~30 | **99 with auto-detect** |
| LLM providers | Proprietary | **Ollama, OpenAI, Anthropic, Groq, any** |
| Open source | No | **MIT License** |
| Platform | Mac, Windows, iOS | **Windows, macOS, Linux** |

## How It Works

1. **Speak** — Press `Ctrl+Shift+D` and talk naturally.
2. **Pick a format** — Press `1-8` to reformat (formal, email, bullets, etc.) or just let it auto-insert.
3. **Inserted** — Text appears at your cursor. Press `Enter` to insert now, `Esc` to cancel.

## Features

- **99 Languages** — Auto-detects your language or pick one from the dropdown
- **Local Whisper STT** — faster-whisper with CTranslate2, 4x faster than OpenAI Whisper
- **Smart LLM cleanup** — Removes filler words, fixes grammar, adds punctuation (language-aware)
- **Instant reformatting** — Dictate once, press 1-8 to reformat as email / Slack / bullets / code
- **Works everywhere** — System-wide insertion into any app via clipboard
- **Keyboard-first** — Number keys for formats, Enter to insert, Esc to cancel. No mouse needed
- **Desktop app** — Native Tauri app with dashboard, settings UI, and system tray
- **Privacy first** — Audio never leaves your machine unless you choose a cloud LLM
- **GPU + CPU** — CUDA acceleration when available, fast CPU fallback with int8 quantization

## Download

Grab the latest installer from [Releases](https://github.com/kristerus/dictateme/releases/latest), or build from source below.

## Quick Start

### From Source

```bash
# Clone
git clone https://github.com/kristerus/dictateme.git
cd dictateme

# Install Python backend (CPU mode)
pip install -e ".[cpu]"

# Or with CUDA support
pip install -e ".[cuda]"

# Start the backend server
python -m dictateme.server

# In another terminal, build and run the Tauri app
cd app/src-tauri
cargo run
```

### Requirements

- **Windows 10/11** (macOS/Linux support in progress)
- **Python 3.12+**
- **Rust toolchain** (for building the Tauri app)
- ~500 MB disk for the speech model
- Microphone

## Configuration

DictateMe reads config from `~/.dictateme/config.toml`. Configure via the Settings UI in the app, or edit the file directly.

```toml
[general]
language = "auto"          # "auto" = detect, or "en", "de", "sq", "ja", etc.

[stt]
model = "base"             # tiny | base | small | medium | large-v3
device = "auto"            # auto | cuda | cpu
compute_type = "int8"      # int8 (fast CPU) | float16 (GPU) | float32
beam_size = 1              # 1 = fast greedy, 5 = accurate beam search

[llm]
enabled = false            # true to enable LLM cleanup/reformatting
provider = "ollama"        # ollama | openai | anthropic | groq | custom

[llm.ollama]
model = "llama3.2:3b"

[formatting]
auto_insert_delay_ms = 1500  # 0 = instant, 1500 = show overlay first
```

See [`config.default.toml`](config.default.toml) for all options.

## LLM Setup (Optional)

DictateMe works without an LLM — you get clean Whisper transcription. To enable filler word removal and reformatting:

### Local (Ollama)
```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2:3b
```
Then set `llm.enabled = true` in Settings. Fully offline.

### Cloud Providers
Paste your API key in Settings. Supports OpenAI (GPT-4o-mini), Anthropic (Claude), Groq (Llama), or any OpenAI-compatible endpoint.

## Format Presets

Press a number key after dictating to reformat:

| Key | Format | What it does |
|-----|--------|--------------|
| `1` | As-is | Clean transcript, no changes |
| `2` | Formal | Professional tone |
| `3` | Casual | Friendly, relaxed |
| `4` | Email | With greeting/closing |
| `5` | Bullets | Concise list |
| `6` | Code | `// prefixed` comment lines |
| `7` | AI Prompt | Clear instructions |
| `8` | Slack | Brief and direct |

## Architecture

```
Tauri App (Rust + HTML/CSS/JS)
    ↕ HTTP (localhost:18234)
Python Sidecar Server
    ├── Audio Capture (sounddevice)
    ├── STT (faster-whisper)
    ├── LLM Cleanup (litellm → ollama/openai/anthropic/groq)
    └── Text Insertion (clipboard paste)
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design document.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v           # Run tests
ruff check src/            # Lint
mypy src/                  # Type check
```

## License

[MIT](LICENSE)
