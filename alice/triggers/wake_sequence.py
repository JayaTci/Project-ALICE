"""
Wake word quiet start — triggered by "hey jarvis".

Steps:
  1. Launch preset apps (no music, no tiling — quiet)
  2. Speak a short greeting
  3. Return — caller continues listening for user command
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run(broadcast) -> None:
    """
    Quiet start after wake word detection.

    Args:
        broadcast: async callable(dict) — sends events to all UI clients.
    """
    # Launch apps in background (don't block listening)
    asyncio.create_task(_launch_apps_quiet())

    greeting = _pick_greeting()

    # Stream greeting to UI
    for word in greeting.split():
        await broadcast({"type": "token", "text": word + " "})
        await asyncio.sleep(0.02)
    await broadcast({"type": "done"})

    # Speak greeting, then hand control back
    try:
        from alice.brain.tts import edge_tts as tts
        await tts.speak(greeting)
    except Exception:
        logger.exception("Wake sequence TTS failed")


def _pick_greeting() -> str:
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning boss, I'm listening."
    elif hour < 18:
        return "Good afternoon boss, I'm here."
    else:
        return "Good evening boss, what do you need?"


async def _launch_apps_quiet() -> None:
    """Launch preset apps silently, no tiling."""
    from alice.config import settings
    from alice.tools.apps import PRESET_EXECUTABLES
    import subprocess

    app_names = [a.strip() for a in settings.preset_apps.split(",") if a.strip()]
    for name in app_names:
        exe = PRESET_EXECUTABLES.get(name.lower(), name)
        try:
            subprocess.Popen(exe, shell=True)
            logger.info("Wake: launched %s", name)
        except Exception:
            logger.warning("Wake: failed to launch %s", name)
