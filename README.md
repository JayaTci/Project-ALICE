# Project Alice

Personal JARVIS-inspired AI assistant that lives entirely on your PC. Female voice, bilingual EN/JA, voice-loyal to one user, full PC control, learns from interactions.

---

## Features

| Feature | Status |
|---------|--------|
| Voice + chat input | Done |
| Wake word ("hey alice") | Done |
| Double clap Iron Man boot | Done |
| Speaker verification | Done |
| PC control (apps, volume, lock) | Done |
| Weather, news, file tools | Done |
| Desktop browser UI + system tray | Done |
| Bilingual EN/JA (auto-detect) | Done |
| Memory (/remember, auto-extract) | Done |
| Usage pattern proactive suggestions | Done |
| Global hotkey Ctrl+Shift+A | Done |
| Rotating log files | Done |
| Windows autostart | Done |

---

## Quick Start

### 1. Requirements

- Python 3.14
- Windows 10/11
- [Groq API key](https://console.groq.com) — free, no credit card

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — fill in GROQ_API_KEY at minimum
```

### 4. Run

| Mode | Command |
|------|---------|
| Desktop UI + voice | `py -3.14 alice/main.py --ui` |
| Desktop UI, text only | `py -3.14 alice/main.py --ui --chat` |
| Terminal + voice | `py -3.14 alice/main.py` |
| Terminal text only | `py -3.14 alice/main.py --chat` |
| Skip health check | add `--no-check` to any mode |

The browser opens automatically in UI mode. A system tray icon appears — right-click to quit.

---

## Voice Setup (optional)

### Wake word
Default wake word: `hey alice` (OpenWakeWord, built-in, no account needed).

Custom wake word: set `WAKE_WORD_MODEL` in `.env` to path of your `.onnx` model. Use `scripts/generate_hey_alice.py` + `scripts/train_hey_alice.py` to train one.

### Speaker verification (respond only to your voice)

```bash
py -3.14 scripts/enroll_voice.py
```

Then set `SPEAKER_VERIFY_ENABLED=true` in `.env`.

### Japanese voice input

Set `STT_MODEL_SIZE=small` in `.env` (multilingual Whisper model). Japanese text chat works without this change.

---

## Memory & Learning

Alice remembers things across sessions:

| Command | Effect |
|---------|--------|
| `/remember I prefer dark mode` | Saves preference permanently |
| `/forget dark mode` | Removes matching memories |
| `/memories` | Lists everything Alice remembers |
| `/ja` | Switch to Japanese mode |
| `/en` | Switch to English mode |

Alice also automatically extracts preferences from natural conversation ("I prefer Chrome over Firefox") and learns which tools you use at what time of day to offer proactive suggestions.

---

## Boot Sequence (double clap)

Double clap activates the Iron Man boot:
1. Plays `SHOOT_TO_THRILL_PATH` audio (if configured)
2. Launches all `PRESET_APPS` side-by-side
3. Fetches weather (if `OPENWEATHER_API_KEY` set)
4. Reads top 3 BBC world headlines
5. Speaks the full briefing

---

## Windows Autostart

Install Alice to start automatically at logon:

```bash
py -3.14 scripts/autostart.py install
py -3.14 scripts/autostart.py status
py -3.14 scripts/autostart.py uninstall
```

---

## Architecture

```
Mic -> AudioListener (subprocess)
         |- OpenWakeWord ("hey alice")
         |- Double clap detector
         |- Amplitude VAD -> Faster-Whisper STT
         `- SpeechBrain speaker verify
                |
                | multiprocessing.Queue
                v
        AliceBrain (aiohttp server :8765)
         |- Groq / Ollama LLM (streaming)
         |- 7 tools (PC, files, weather, news, music, apps)
         |- SQLite memory + preferences
         |- Usage pattern tracker
         `- Edge-TTS voice output (EN + JA)
                |
                | WebSocket
                v
        Browser UI
         |- Canvas orb visualization (5 states)
         |- Streaming chat log + EN subtitle (JA mode)
         |- EN/JA toggle + settings panel
         `- System tray (pystray)
```

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.14 |
| LLM (cloud) | Groq API / llama-3.3-70b-versatile |
| LLM (local) | Ollama / llama3.1:8b |
| STT | Faster-Whisper (local CPU) |
| TTS | Edge-TTS (EN: AriaNeural, JA: NanamiNeural) |
| Wake word | OpenWakeWord (MIT license) |
| Speaker verify | SpeechBrain ECAPA-TDNN |
| UI server | aiohttp + Vanilla JS |
| Memory | SQLite (aiosqlite) |
| Audio | sounddevice + NumPy |
| PC control | subprocess + psutil + ctypes |
| System tray | pystray + Pillow |
| Hotkey | keyboard |

---

## File Structure

```
Alice_Project/
|- alice/
|   |- main.py              # Entry point
|   |- config.py            # Pydantic settings (.env)
|   |- persona.yaml         # Alice personality
|   |- server.py            # aiohttp HTTP + WebSocket
|   |- tray.py              # System tray icon
|   |- brain/               # LLM engine, STT, TTS, providers, language
|   |- audio/               # Mic, wake word, VAD, speaker verify
|   |- memory/              # SQLite, preferences, patterns, context builder
|   |- tools/               # 7 PC control / web tools
|   |- triggers/            # Boot sequence, wake sequence, hotkey
|   `- utils/               # Health check, logging setup
|- ui/
|   |- index.html           # Single-page app
|   |- styles/alice.css     # Dark glassmorphism theme
|   `- js/                  # voice-viz, chat, settings, websocket
|- scripts/
|   |- enroll_voice.py      # Voice enrollment wizard
|   |- autostart.py         # Windows Task Scheduler installer
|   |- generate_hey_alice.py
|   `- train_hey_alice.py
|- logs/                    # Rotating log files (gitignored)
|- data/                    # DB + models (gitignored)
|- requirements.txt
`- .env.example
```

---

## Troubleshooting

**Alice won't start** — run health check: `py -3.14 alice/main.py --no-check` skips it. Or read the output to see what's missing.

**Voice not working** — install audio deps: `pip install sounddevice faster-whisper openwakeword edge-tts`

**Wake word too sensitive / not triggering** — adjust `WAKE_WORD_THRESHOLD` in `.env` (0.3 = sensitive, 0.7 = strict)

**Japanese not working in voice** — set `STT_MODEL_SIZE=small` in `.env` (downloads ~240MB multilingual model on first use)

**LLM errors** — check `logs/alice.log` for details. Common causes: expired API key, rate limit, no internet.

---

## Phase Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Foundation | Done |
| 1 | Text chat brain | Done |
| 2 | Tool system | Done |
| 3 | Voice input | Done |
| 3.5 | Custom wake word training | Done |
| 4 | Voice output (TTS) | Done |
| 5 | Speaker verification | Done |
| 6 | Desktop UI | Done |
| 7 | Trigger sequences | Done |
| 8 | Bilingual EN/JA | Done |
| 9 | Memory & learning | Done |
| 10 | Polish & hardening | Done |

---

## License

Personal project. Not for redistribution.
