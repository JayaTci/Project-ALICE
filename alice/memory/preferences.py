"""
Preference management — Phase 9.

Handles:
  - /remember <thing>  — explicit user command
  - Auto-extraction    — keyword-triggered background LLM extraction
  - Preference deletion via /forget
"""

import asyncio
import logging
import re
from datetime import datetime

from alice.memory.store import delete_preference, get_all_preferences, set_preference

logger = logging.getLogger(__name__)

# Keywords that signal a preference worth extracting
_PREF_KEYWORDS = re.compile(
    r"\b(prefer|like|love|hate|always|never|favorite|favourite|usually|tend to|"
    r"enjoy|don't like|dislike|prefer not|want|need|use)\b",
    re.IGNORECASE,
)


# ── /remember command ─────────────────────────────────────────────────────────

async def handle_remember(text: str) -> str:
    """
    Parse '/remember <thing>' and save it.
    Returns confirmation string to yield back to user.

    The raw statement is saved as a preference. The LLM reads it in future
    sessions naturally through the preferences block in the system prompt.
    """
    thing = text.strip()
    if not thing:
        return "What should I remember? Usage: /remember <something>"

    # Generate a short stable key from the content
    key = _make_key(thing)
    await set_preference(key, thing, confidence=1.0)
    logger.info("Remembered: %s = %r", key, thing)
    return f"Got it, boss. I'll remember: \"{thing}\""


async def handle_forget(text: str) -> str:
    """
    Parse '/forget <keyword>' and remove matching preferences.
    """
    keyword = text.strip().lower()
    if not keyword:
        return "What should I forget? Usage: /forget <keyword>"

    prefs = await get_all_preferences()
    removed = []
    for key, val in prefs.items():
        if keyword in key.lower() or keyword in val.lower():
            await delete_preference(key)
            removed.append(val)

    if removed:
        return f"Forgotten: {', '.join(repr(r) for r in removed)}"
    return f"I don't have anything matching \"{keyword}\" in my memory."


async def list_memories() -> str:
    """Return formatted list of all remembered preferences."""
    prefs = await get_all_preferences()
    if not prefs:
        return "I don't have anything saved in my memory yet."
    lines = [f"• {v}" for v in prefs.values()]
    return "Here's what I remember about you:\n" + "\n".join(lines)


# ── Auto-extraction (background, non-blocking) ────────────────────────────────

def should_extract(user_input: str) -> bool:
    """Quick keyword check — only run LLM extraction if likely to find a preference."""
    return bool(_PREF_KEYWORDS.search(user_input))


async def extract_and_save(user_input: str) -> None:
    """
    Background task: ask LLM to extract a preference from user_input.
    Saves result if extraction is confident. Fails silently.
    """
    try:
        from alice.brain.llm.router import get_provider
        from alice.brain.llm.base import Message

        provider = get_provider()
        messages = [
            Message(
                role="system",
                content=(
                    "Extract an explicit preference or personal fact from the user's message. "
                    "Return a JSON object with ONE key-value pair, e.g. {\"browser\": \"Chrome\"} "
                    "or {\"favorite_game\": \"Elden Ring\"} or {\"wake_up_time\": \"7am\"}. "
                    "Keys: snake_case, short, descriptive. Values: concise. "
                    "Only extract EXPLICIT, clear preferences. "
                    "Return null (not JSON) if there is no clear preference to extract."
                ),
            ),
            Message(role="user", content=user_input),
        ]

        result = await provider.complete(messages, tools=None)
        raw = (result.content or "").strip()

        if not raw or raw.lower() == "null":
            return

        import json
        # Find JSON object in response
        match = re.search(r"\{[^}]+\}", raw)
        if not match:
            return

        data = json.loads(match.group())
        for key, value in data.items():
            if key and value and len(str(value)) < 200:
                clean_key = re.sub(r"[^a-z0-9_]", "_", str(key).lower())[:50]
                await set_preference(clean_key, str(value), confidence=0.8)
                logger.info("Auto-extracted preference: %s = %r", clean_key, value)

    except Exception:
        logger.debug("Preference extraction failed (non-critical)", exc_info=True)


def schedule_extraction(user_input: str) -> None:
    """Fire-and-forget: schedule preference extraction as background task."""
    if should_extract(user_input):
        asyncio.create_task(extract_and_save(user_input))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_key(text: str) -> str:
    """Generate a short stable key from raw text."""
    # Use first few words + timestamp suffix for uniqueness
    words = re.sub(r"[^a-z0-9 ]", "", text.lower()).split()
    base = "_".join(words[:4]) or "memory"
    suffix = datetime.now().strftime("%m%d%H%M")
    return f"{base}_{suffix}"[:60]
