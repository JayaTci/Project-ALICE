"""
Alice — UI Server (Phase 6)

Serves the web UI as static files and handles real-time communication
via WebSocket. Both chat input (from UI) and voice events (from AudioListener)
flow through this server.

Architecture:
  aiohttp HTTP server  →  ui/index.html + static files
  aiohttp WebSocket    →  real-time chat + status events
  AudioListener queue  →  polled and broadcast to all WS clients

Usage (via main.py):
  py -3.14 alice/main.py --ui        # voice + UI
  py -3.14 alice/main.py --ui --chat # UI only (no mic)
"""

import asyncio
import json
import logging
import webbrowser
from pathlib import Path

from aiohttp import web, WSMsgType

logger = logging.getLogger(__name__)

UI_DIR = Path(__file__).parent.parent / "ui"
HOST = "localhost"
PORT = 8765

# Active WebSocket connections
_ws_clients: set[web.WebSocketResponse] = set()

# Serialize all brain calls — prevents concurrent LLM requests
_brain_lock = asyncio.Lock()


# ─── Broadcast helpers ──────────────────────────────────────────────────────

async def broadcast(message: dict) -> None:
    """Send JSON message to all connected UI clients."""
    if not _ws_clients:
        return
    data = json.dumps(message)
    dead: set[web.WebSocketResponse] = set()
    for ws in _ws_clients:
        try:
            await ws.send_str(data)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def broadcast_status(state: str, label: str = "") -> None:
    await broadcast({"type": "status", "state": state, "label": label})


# ─── Brain response handler ─────────────────────────────────────────────────

async def _run_brain(brain, text: str, speak: bool = False) -> None:
    """
    Stream brain response to all UI clients.
    speak=True → also play TTS in the current language after streaming.
    JA mode: strips [EN: ...] subtitle before speaking (UI keeps it for subtitle display).
    """
    import re as _re
    full_response = ""
    async for chunk in brain.respond_stream(text):
        await broadcast({"type": "token", "text": chunk})
        full_response += chunk
    await broadcast({"type": "done"})

    if speak and full_response:
        await broadcast_status("speaking")
        from alice.brain.tts import edge_tts as tts
        from alice.brain.language import get_language
        lang = get_language()
        # Strip [EN: ...] block before TTS so Alice only speaks the primary language
        tts_text = _re.sub(r'\s*\[EN:[\s\S]*?\]\s*$', '', full_response).strip()
        if tts_text:
            await tts.speak(tts_text, language=lang)
        await broadcast_status("idle")


# ─── WebSocket handler ───────────────────────────────────────────────────────

async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket connections from the UI."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _ws_clients.add(ws)
    logger.info("UI client connected (%d total)", len(_ws_clients))

    # Sync current language to new client
    from alice.brain.language import get_language
    await ws.send_str(json.dumps({"type": "language_changed", "lang": get_language()}))

    brain = request.app["brain"]

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "message":
                    text = data.get("text", "").strip()
                    if not text:
                        continue
                    await _handle_chat_message(brain, text)

                elif msg_type == "set_language":
                    lang = data.get("lang", "en")
                    if lang in {"en", "ja"}:
                        from alice.brain.language import set_language, get_language
                        set_language(lang)
                        await broadcast({"type": "language_changed", "lang": lang})
                        logger.info("Language set to: %s", lang)

                elif msg_type == "ping":
                    await ws.send_str(json.dumps({"type": "pong"}))

            elif msg.type == WSMsgType.ERROR:
                logger.error("WebSocket error: %s", ws.exception())
    finally:
        _ws_clients.discard(ws)
        logger.info("UI client disconnected (%d remaining)", len(_ws_clients))

    return ws


async def _handle_chat_message(brain, text: str) -> None:
    """Process user text from UI chat input."""
    from alice.config import settings

    # Owner PIN → skip brain, run full boot sequence (same as double clap)
    if settings.owner_pin and text.strip() == settings.owner_pin:
        async with _brain_lock:
            await broadcast({"type": "token", "text": "Owner verified. Running boot sequence..."})
            await broadcast({"type": "done"})
            await broadcast_status("thinking", "Boot sequence...")
            try:
                from alice.triggers.boot_sequence import run as boot_run
                await boot_run(broadcast)
            except Exception:
                logger.exception("Boot sequence error via owner PIN")
            finally:
                await broadcast_status("idle")
        return

    async with _brain_lock:
        await broadcast_status("thinking")
        try:
            await _run_brain(brain, text, speak=True)
        except Exception as exc:
            logger.exception("Brain error processing chat message")
            await broadcast({"type": "error", "message": str(exc)})
            await broadcast_status("idle")


# ─── Voice event handler ─────────────────────────────────────────────────────

async def _poll_voice_events(listener, brain) -> None:
    """
    Background task: poll AudioListener subprocess queue and
    broadcast events to all connected UI clients.
    """
    from alice.audio.listener import EventType

    loop = asyncio.get_event_loop()

    while True:
        event = await loop.run_in_executor(None, listener.get_event, 0.1)
        if event is None:
            continue

        if event.type == EventType.WAKE_WORD:
            await broadcast({"type": "wake_word"})
            async with _brain_lock:
                # Phase 7: run quiet wake sequence (apps + greeting)
                try:
                    from alice.triggers.wake_sequence import run as wake_run
                    await broadcast_status("thinking", "Starting up…")
                    await wake_run(broadcast)
                except Exception:
                    logger.exception("Wake sequence error")
                finally:
                    await broadcast_status("listening", "Listening…")

        elif event.type == EventType.TRANSCRIPT:
            text = event.text
            logger.info("Voice transcript: %r", text)
            await broadcast({"type": "transcript", "text": text})
            async with _brain_lock:
                await broadcast_status("thinking")
                try:
                    await _run_brain(brain, text, speak=True)
                except Exception as exc:
                    logger.exception("Brain error processing voice")
                    await broadcast({"type": "error", "message": str(exc)})
                finally:
                    await broadcast_status("idle")

        elif event.type == EventType.DOUBLE_CLAP:
            # Phase 7: Iron Man boot sequence
            async with _brain_lock:
                try:
                    from alice.triggers.boot_sequence import run as boot_run
                    await boot_run(broadcast)
                except Exception as exc:
                    logger.exception("Boot sequence error")
                    await broadcast({"type": "error", "message": str(exc)})
                    await broadcast_status("idle")

        elif event.type == EventType.ERROR:
            logger.error("Audio error: %s", event.error)
            await broadcast({"type": "error", "message": event.error})


# ─── HTTP routes ─────────────────────────────────────────────────────────────

async def _index_handler(request: web.Request) -> web.FileResponse:
    return web.FileResponse(UI_DIR / "index.html")


async def _config_handler(request: web.Request) -> web.Response:
    """Return a safe subset of settings as JSON for the UI settings panel."""
    from alice.config import settings
    from alice.brain.language import get_language
    data = {
        "llm_provider": settings.llm_provider,
        "groq_model": settings.groq_model,
        "wake_word_model": settings.wake_word_model,
        "stt_model_size": settings.stt_model_size,
        "stt_model_size_ja": settings.stt_model_size_ja,
        "speaker_verify_enabled": settings.speaker_verify_enabled,
        "weather_city": settings.weather_city,
        "weather_country_code": settings.weather_country_code,
        "language": get_language(),
    }
    return web.json_response(data)


def _make_app(brain) -> web.Application:
    app = web.Application()
    app["brain"] = brain

    # WebSocket
    app.router.add_get("/ws", ws_handler)

    # REST
    app.router.add_get("/api/config", _config_handler)

    # Static UI files
    app.router.add_get("/", _index_handler)
    app.router.add_static("/styles", UI_DIR / "styles")
    app.router.add_static("/js", UI_DIR / "js")

    return app


# ─── Entry point ─────────────────────────────────────────────────────────────

async def run_ui_mode(voice_enabled: bool = True) -> None:
    """
    Full UI mode:
      - Starts HTTP + WebSocket server
      - Optionally starts AudioListener voice processing
      - Opens browser
    """
    from alice.config import settings
    from alice.memory.store import create_session, init_db
    from alice.brain.engine import AliceBrain
    from alice.brain.language import set_language

    # Seed language from config
    if settings.default_language != "en":
        set_language(settings.default_language)

    await init_db()
    session_id = await create_session()
    brain = AliceBrain(session_id=session_id)
    brain.enable_tools()

    # Start aiohttp server
    app = _make_app(brain)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    logger.info("Alice UI server at http://%s:%d", HOST, PORT)

    # Open browser (slight delay so server is ready)
    await asyncio.sleep(0.4)
    webbrowser.open(f"http://{HOST}:{PORT}")
    logger.info("Browser opened.")

    # Phase 7: global hotkey Ctrl+Shift+A
    loop = asyncio.get_event_loop()
    try:
        from alice.triggers.hotkey import start_hotkey_listener
        from alice.triggers.wake_sequence import run as wake_run

        async def _hotkey_trigger():
            async with _brain_lock:
                await broadcast_status("thinking", "Hotkey triggered…")
                try:
                    await wake_run(broadcast)
                except Exception:
                    logger.exception("Hotkey wake sequence error")
                finally:
                    await broadcast_status("idle")

        start_hotkey_listener(loop, _hotkey_trigger)
        logger.info("Global hotkey Ctrl+Shift+A registered.")
    except Exception:
        logger.warning("Hotkey listener could not start (may need admin rights).")

    if voice_enabled:
        from alice.audio.listener import AudioListener
        listener = AudioListener(
            wake_word_model=settings.wake_word_model,
            wake_word_threshold=settings.wake_word_threshold,
            stt_model_size=settings.stt_model_size,
            language="en",
            speaker_verify=settings.speaker_verify_enabled,
            speaker_threshold=settings.speaker_verify_threshold,
        )
        listener.start()
        logger.info("Voice listener started.")
        await broadcast_status("idle", "Ready")

        try:
            await _poll_voice_events(listener, brain)
        finally:
            listener.stop()
    else:
        # No voice — just keep server alive
        await broadcast_status("idle", "Ready (text only)")
        await asyncio.Event().wait()
