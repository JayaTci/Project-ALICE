"""
Structured logging with rotating file handler — Phase 10.

Call setup_logging() once at startup (before any other imports that log).
Writes to both console (INFO) and logs/alice.log (DEBUG, rotates at 5MB).
"""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure root logger:
      - Console handler: INFO level, concise format
      - File handler:    DEBUG level, full format, rotating (5MB × 3 backups)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers filter

    # ── Formatters ─────────────────────────────────────────────────────
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ─────────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(console_fmt)

    # ── File handler (rotating) ─────────────────────────────────────────
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "alice.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_fmt)

    # ── Attach (clear existing handlers first) ──────────────────────────
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)

    # ── Suppress noisy third-party loggers ──────────────────────────────
    for noisy in ("httpx", "httpcore", "faster_whisper", "speechbrain", "torch"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("alice").info(
        "Logging configured — console: %s, file: %s", log_level, log_file
    )
