"""
Alice — System Tray (Phase 6)

Provides a system tray icon with:
  - Show / Hide window (via webbrowser.open)
  - Quit

Run in a daemon thread alongside the main asyncio loop.
"""

import logging
import threading
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw

from alice.server import HOST, PORT

logger = logging.getLogger(__name__)

_ICON_SIZE = 64
_PURPLE = (124, 58, 237)
_DARK = (15, 15, 26)


def _make_icon() -> Image.Image:
    """Draw a simple purple circle icon for the tray."""
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer ring
    margin = 4
    draw.ellipse(
        [margin, margin, _ICON_SIZE - margin, _ICON_SIZE - margin],
        fill=_PURPLE,
    )
    # Inner dark circle (hollow look)
    inner = margin + 10
    draw.ellipse(
        [inner, inner, _ICON_SIZE - inner, _ICON_SIZE - inner],
        fill=_DARK,
    )
    return img


def _open_ui() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


def start_tray(quit_callback) -> threading.Thread:
    """
    Start pystray in a daemon thread.

    Args:
        quit_callback: Callable invoked when user chooses Quit from tray.
    """
    import pystray

    icon_image = _make_icon()

    menu = pystray.Menu(
        pystray.MenuItem("Open Alice", lambda: _open_ui()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda: _on_quit(icon_ref, quit_callback)),
    )

    icon_ref = pystray.Icon(
        name="Alice",
        icon=icon_image,
        title="Alice — AI Assistant",
        menu=menu,
    )

    def _run():
        icon_ref.run()

    t = threading.Thread(target=_run, daemon=True, name="alice-tray")
    t.start()
    logger.info("System tray started.")
    return t


def _on_quit(icon, callback) -> None:
    icon.stop()
    if callback:
        callback()
