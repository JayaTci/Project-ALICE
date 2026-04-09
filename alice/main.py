"""
Alice — Personal AI Assistant
Entry point.

Modes:
  py alice/main.py          → voice mode (mic + wake word), terminal output
  py alice/main.py --chat   → terminal text chat only (no mic needed)
  py alice/main.py --ui     → desktop UI (voice + browser window)
  py alice/main.py --ui --chat  → desktop UI (text-only, no mic)
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alice.config import settings
from alice.memory.store import create_session, init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alice")

CHAT_MODE = "--chat" in sys.argv
UI_MODE   = "--ui"   in sys.argv


# ─── TERMINAL CHAT LOOP (Phase 1+) ─────────────────────────────────────────

async def _terminal_loop() -> None:
    from alice.brain.engine import AliceBrain

    await init_db()
    session_id = await create_session()
    brain = AliceBrain(session_id=session_id)
    brain.enable_tools()

    logger.info("Alice online. Session: %s", session_id)
    logger.info("Provider: %s | Type 'exit' to quit.\n", settings.llm_provider)

    print("─" * 50)
    print("  Alice — Personal AI Assistant  [TEXT MODE]")
    print("─" * 50)
    print("  Type your message and press Enter.")
    print("  Type 'exit' or Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAlice: Goodbye, boss.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            print("Alice: Goodbye, boss.")
            break

        print("Alice: ", end="", flush=True)
        async for chunk in brain.respond_stream(user_input):
            print(chunk, end="", flush=True)
        print()


# ─── VOICE LOOP (Phase 3+) ──────────────────────────────────────────────────

async def _voice_loop() -> None:
    from alice.audio.listener import AudioListener, EventType
    from alice.brain.engine import AliceBrain
    from alice.brain.tts import edge_tts as tts

    await init_db()
    session_id = await create_session()
    brain = AliceBrain(session_id=session_id)
    brain.enable_tools()

    listener = AudioListener(
        wake_word_model=settings.wake_word_model,
        wake_word_threshold=settings.wake_word_threshold,
        stt_model_size=settings.stt_model_size,
        language="en",
        speaker_verify=settings.speaker_verify_enabled,
        speaker_threshold=settings.speaker_verify_threshold,
    )

    print("─" * 50)
    print("  Alice — Personal AI Assistant  [VOICE MODE]")
    print("─" * 50)
    print(f"  Wake word: '{settings.wake_word_model}'")
    print("  Double clap: ENABLED (Iron Man boot)")
    print("  Hotkey: Ctrl+Shift+A")
    print("  Ctrl+C to quit.\n")

    listener.start()
    print("Alice: Listening...")

    # Phase 7: global hotkey in terminal voice mode
    loop = asyncio.get_event_loop()
    try:
        from alice.triggers.hotkey import start_hotkey_listener
        from alice.triggers.wake_sequence import run as wake_run

        async def _hotkey_trigger():
            print("\n[Ctrl+Shift+A — wake sequence triggered]")
            await wake_run(lambda _: None)  # no UI broadcast in terminal mode

        start_hotkey_listener(loop, _hotkey_trigger)
        logger.info("Hotkey Ctrl+Shift+A registered.")
    except Exception:
        logger.warning("Hotkey listener unavailable.")

    try:
        while True:
            event = await loop.run_in_executor(
                None, lambda: listener.get_event(timeout=0.5)
            )
            if event is None:
                continue

            if event.type == EventType.WAKE_WORD:
                print("\n[Wake word — running quiet start...]")
                from alice.triggers.wake_sequence import run as wake_run
                await wake_run(lambda _: None)
                print("[Listening for command...]")

            elif event.type == EventType.DOUBLE_CLAP:
                print("\n[Double clap — Iron Man boot sequence!]")
                from alice.triggers.boot_sequence import run as boot_run

                async def _print_broadcast(msg):
                    if msg.get("type") == "token":
                        print(msg["text"], end="", flush=True)
                    elif msg.get("type") == "done":
                        print()

                await boot_run(_print_broadcast)

            elif event.type == EventType.TRANSCRIPT:
                text = event.text
                print(f"\nYou: {text}")
                print("Alice: ", end="", flush=True)
                full_response = ""
                async for chunk in brain.respond_stream(text):
                    print(chunk, end="", flush=True)
                    full_response += chunk
                print()
                if full_response:
                    await tts.speak(full_response)

            elif event.type == EventType.ERROR:
                logger.error("Audio error: %s", event.error)

    except KeyboardInterrupt:
        print("\nAlice: Goodbye, boss.")
    finally:
        listener.stop()


# ─── UI MODE (Phase 6+) ──────────────────────────────────────────────────────

async def _ui_loop() -> None:
    from alice.server import run_ui_mode
    from alice.tray import start_tray

    stop_event = asyncio.Event()

    def _quit():
        stop_event.set()

    start_tray(_quit)

    print("─" * 50)
    print("  Alice — Personal AI Assistant  [UI MODE]")
    print("─" * 50)
    print("  Browser window will open automatically.")
    print("  System tray icon: right-click to quit.\n")

    voice_enabled = not CHAT_MODE
    try:
        await run_ui_mode(voice_enabled=voice_enabled)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


# ─── ENTRY POINT ────────────────────────────────────────────────────────────

def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()

    if UI_MODE:
        asyncio.run(_ui_loop())
    elif CHAT_MODE:
        asyncio.run(_terminal_loop())
    else:
        asyncio.run(_voice_loop())


if __name__ == "__main__":
    main()
