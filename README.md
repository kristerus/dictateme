# DictateMe

**System-wide voice dictation for Windows. Local-first. Free. Open source.**

Hold **Ctrl+Win**, speak naturally, release — polished text appears wherever your cursor is.

[Website](https://dictateme.org) · [Download](https://github.com/kristerus/dictateme/releases/latest) · [Report Bug](https://github.com/kristerus/dictateme/issues)

---

## Why DictateMe?

|  | **Wispr Flow** | **DictateMe** |
|---|---|---|
| Price | $10–20/month | **Free forever** |
| Speech-to-text | Cloud (their servers) | **Local (your machine)** |
| Works offline | No | **Yes** |
| Audio privacy | Sent to cloud | **Never leaves your PC** |
| LLM providers | Proprietary | **Ollama, OpenAI, Anthropic, Groq, any** |
| Open source | No | **MIT License** |

## How It Works

1. **Speak** — Hold `Ctrl+Win` and talk naturally. VAD captures only your voice.
2. **Process** — Whisper transcribes locally. An LLM cleans up filler words, fixes grammar.
3. **Insert** — Polished text is inserted wherever your cursor is. Pick a format or let it auto-insert.

## Features

- **Local Whisper STT** — faster-whisper with CTranslate2, 4x faster than OpenAI Whisper
- **Smart LLM cleanup** — removes "um", "uh", "like", fixes grammar, adds punctuation
- **Instant reformatting** — dictate once, reformat as email / Slack / bullets / code comments
- **Works everywhere** — system-wide insertion into any app via clipboard or SendInput
- **Privacy first** — audio never leaves your machine unless you choose a cloud LLM
- **GPU + CPU** — CUDA acceleration when available, fast CPU fallback

## Quick Start

### From Source

```bash
# Clone
git clone https://github.com/kristerus/dictateme.git
cd dictateme

# Install (CPU mode)
pip install -e ".[cpu]"

# Or with CUDA support
pip install -e ".[cuda]"

# Run
python -m dictateme
```

### Download

Grab the latest `.exe` from [Releases](https://github.com/kristerus/dictateme/releases/latest).

## Configuration

DictateMe reads config from `~/.dictateme/config.toml`. On first run, defaults are used.

```toml
[hotkey]
mode = "hold"              # "hold" (push-to-talk) or "toggle"
key_combo = "ctrl+windows"

[stt]
model = "small.en"         # tiny.en | small.en | medium.en | large-v3
device = "auto"            # auto | cuda | cpu

[llm]
enabled = true
provider = "ollama"        # ollama | openai | anthropic | groq | custom

[llm.ollama]
model = "llama3.2:3b"
```

See [`config.default.toml`](config.default.toml) for all options.

## Format Presets

Press a number key after dictating to reformat:

| Key | Format | Example output |
|-----|--------|----------------|
| `1` | As-is | Clean transcript |
| `2` | Formal | Professional tone |
| `3` | Casual | Friendly, relaxed |
| `4` | Email | With greeting/closing |
| `5` | Bullet points | Concise list |
| `6` | Code comment | `// prefixed lines` |
| `7` | AI prompt | Clear instructions |
| `8` | Slack message | Brief and direct |

## System Requirements

- Windows 10/11
- Python 3.12+ (if running from source)
- ~500 MB disk for the `small.en` model
- Microphone
- Optional: NVIDIA GPU for faster transcription

## Architecture

```
Hotkey → Audio Capture → VAD → STT (faster-whisper) → LLM cleanup → Text Insertion
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design document.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v           # Run tests
ruff check src/            # Lint
mypy src/                  # Type check
python scripts/build.py    # Build .exe
```

## License

[MIT](LICENSE)
