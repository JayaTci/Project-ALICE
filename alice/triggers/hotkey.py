"""
Global hotkey listener — Ctrl+Shift+A

Triggers the wake sequence (quiet start) from anywhere on the desktop.
Runs in a daemon thread so it doesn't block the asyncio loop.

Usage:
    from alice.triggers.hotkey import start_hotkey_listener
    start_hotkey_listener(asyncio_loop, on_trigger_coro_factory)
"""

import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

HOTKEY = "ctrl+shift+a"


def start_hotkey_listener(loop: asyncio.AbstractEventLoop, on_trigger) -> threading.Thread:
    """
    Start listening for Ctrl+Shift+A in a background daemon thread.

    Args:
        loop:       The running asyncio event loop.
        on_trigger: Async callable (no args) to schedule on the loop when hotkey fires.
                    E.g. lambda: wake_sequence.run(broadcast)

    Returns:
        The daemon thread (already started).
    """
    import keyboard

    def _listen():
        logger.info("Hotkey listener active: %s", HOTKEY)
        keyboard.add_hotkey(HOTKEY, lambda: _fire(loop, on_trigger))
        keyboard.wait()  # blocks thread forever

    t = threading.Thread(target=_listen, daemon=True, name="alice-hotkey")
    t.start()
    return t


def _fire(loop: asyncio.AbstractEventLoop, coro_factory) -> None:
    """Schedule the coroutine on the asyncio event loop from the hotkey thread."""
    logger.info("Hotkey %s fired", HOTKEY)
    asyncio.run_coroutine_threadsafe(coro_factory(), loop)
