# Project Alice

Personal JARVIS-inspired AI assistant that lives on your PC. Female voice, bilingual EN/JA, voice-loyal to one user, full PC control.

---

## Features

- **Voice + chat** — mic input or browser chat, always responds via voice + UI
- **Wake word** — "Hey Jarvis" via OpenWakeWord (no account needed)
- **Double clap** — triggers Iron Man boot sequence (music + apps + briefing)
- **Speaker verification** — only Chester's voice accepted (SpeechBrain ECAPA-TDNN)
- **PC control** — open/close apps, volume, lock screen, system info
- **Web tools** — weather, world + PH news via RSS, file operations
- **Desktop UI** — dark glassmorphism browser UI, canvas orb visualization, system tray
- **Memory** — SQLite conversation history + user preferences
- **Bilingual** — EN/JA support (Phase 8, planned)

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add GROQ_API_KEY at minimum
```

### 3. Run

| Mode | Command |
|------|---------|
| Desktop UI + voice | `py -3.14 alice/main.py --ui` |
| Desktop UI, text only | `py -3.14 alice/main.py --ui --chat` |
| Terminal + voice | `py -3.14 alice/main.py` |
| Terminal text only | `py -3.14 alice/main.py --chat` |

---

## Requirements

- Python 3.14
- [Groq API key](https://console.groq.com) — free tier, no credit card
- Windows 10/11

Optional:
- Ollama (local LLM on desktop, set `LLM_PROVIDER=ollama` in `.env`)
- OpenWeatherMap API key (for weather tool)

---

## Voice Enrollment (one-time setup)

To enable speaker verification (Alice only responds to your voice):

```bash
py -3.14 scripts/enroll_voice.py
```

Then set `SPEAKER_VERIFY_ENABLED=true` in `.env`.

---

## Architecture

```
Mic → AudioListener (subprocess)
        ├── OpenWakeWord ("hey jarvis")
        ├── Double clap detector
        ├── Amplitude VAD → Faster-Whisper STT
        └── SpeechBrain speaker verify
                │
                │ multiprocessing.Queue
                ▼
        AliceBrain (aiohttp server)
        ├── Groq / Ollama LLM (streaming)
        ├── Tool system (7 tools)
        ├── SQLite memory
        └── Edge-TTS voice output
                │
                │ WebSocket (localhost:8765)
                ▼
        Browser UI
        ├── Canvas orb visualization
        ├── Streaming chat log
        └── Settings panel
```

---

## Phase Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Foundation (config, persona, project structure) | ✅ Done |
| 1 | Text chat brain (Groq/Ollama, SQLite memory) | ✅ Done |
| 2 | Tool system (PC control, weather, news, files) | ✅ Done |
| 3 | Voice input (STT, wake word, clap detection) | ✅ Done |
| 3.5 | Custom "hey alice" wake word training | ✅ Done |
| 4 | Voice output (Edge-TTS) | ✅ Done |
| 5 | Speaker verification (SpeechBrain ECAPA-TDNN) | ✅ Done |
| 6 | Desktop UI (aiohttp + browser + pystray) | ✅ Done |
| 7 | Trigger sequences (Iron Man boot, hotkey) | Pending |
| 8 | Bilingual EN/JA | Pending |
| 9 | Memory & learning | Pending |
| 10 | Polish & hardening | Pending |

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.14 |
| LLM (cloud) | Groq API — llama-3.3-70b-versatile |
| LLM (local) | Ollama — llama3.1:8b |
| STT | Faster-Whisper (local, CPU) |
| TTS | Edge-TTS (Microsoft neural, EN + JA) |
| Wake word | OpenWakeWord (MIT license) |
| Speaker verify | SpeechBrain ECAPA-TDNN |
| UI server | aiohttp + Vanilla JS |
| Memory | SQLite (aiosqlite) |
| Audio | sounddevice + NumPy |
| PC control | subprocess + psutil + ctypes |
| System tray | pystray + Pillow |

---

## Project Structure

```
Alice_Project/
├── alice/
│   ├── main.py              # Entry point
│   ├── config.py            # Pydantic settings (.env)
│   ├── persona.yaml         # Alice personality
│   ├── server.py            # aiohttp HTTP + WebSocket server
│   ├── tray.py              # System tray icon
│   ├── brain/               # LLM engine, STT, TTS, providers
│   ├── audio/               # Mic listener, wake word, VAD, speaker verify
│   ├── memory/              # SQLite store + context builder
│   └── tools/               # 7 PC control / web tools
├── ui/
│   ├── index.html           # Single-page app
│   ├── styles/alice.css     # Dark glassmorphism theme
│   └── js/                  # voice-viz, chat, settings, websocket
├── scripts/
│   ├── enroll_voice.py      # Voice enrollment wizard
│   ├── generate_hey_alice.py
│   └── train_hey_alice.py
├── requirements.txt
└── .env.example
```

---

## License

Personal project — not for redistribution.
