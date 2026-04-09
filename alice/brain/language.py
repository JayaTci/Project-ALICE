"""
Language manager — Phase 8.

Tracks current language (EN/JA), auto-detects from user input,
and supports manual override via command or UI toggle.

Usage:
    from alice.brain.language import get_language, update_from_input, set_language
"""

import re
import threading

# Japanese: hiragana, katakana, common kanji ranges
_JA_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")

# Commands that explicitly switch language
_FORCE_JA = {"/ja", "switch to japanese", "日本語で話して", "日本語モード"}
_FORCE_EN = {"/en", "/english", "switch to english", "英語で話して", "英語モード"}

_lock = threading.Lock()
_current: str = "en"
_auto: bool = True   # True = auto-detect from each input; False = locked to _current


# ── Public API ────────────────────────────────────────────────────────────────

def detect(text: str) -> str:
    """Return 'ja' if text contains Japanese characters, else 'en'."""
    return "ja" if _JA_PATTERN.search(text) else "en"


def is_language_command(text: str) -> str | None:
    """
    Check if text is a language-switch command.
    Returns 'ja', 'en', or None.
    """
    normalized = text.strip().lower()
    if normalized in _FORCE_JA:
        return "ja"
    if normalized in _FORCE_EN:
        return "en"
    return None


def update_from_input(text: str) -> str:
    """
    Auto-detect language from user input and update state (if auto mode).
    Returns the current language after update.
    """
    global _current, _auto
    with _lock:
        if _auto:
            _current = detect(text)
        return _current


def set_language(lang: str) -> None:
    """Manually lock language. Disables auto-detect until reset_auto() is called."""
    global _current, _auto
    with _lock:
        _current = lang
        _auto = False


def reset_auto() -> None:
    """Re-enable auto-detection from user input."""
    global _auto
    with _lock:
        _auto = True


def get_language() -> str:
    with _lock:
        return _current


def is_auto() -> bool:
    with _lock:
        return _auto
