"""
Usage pattern analysis + proactive suggestions — Phase 9.

Tracks what tools/apps Chester uses and when.
Generates time-aware suggestions injected into the LLM context.

Event types:
  tool_call   — detail = "tool_name"
  app_launch  — detail = "app_name"
  voice_wake  — detail = "wake_word" | "clap" | "hotkey"
"""

import logging
from datetime import datetime

from alice.memory.store import get_usage_stats, log_usage

logger = logging.getLogger(__name__)

# Minimum occurrences before suggesting
SUGGESTION_THRESHOLD = 3

# Human-readable app/tool descriptions
_TOOL_LABELS: dict[str, str] = {
    "get_weather": "check the weather",
    "get_news": "read the news",
    "launch_apps": "launch your apps",
    "pc_control": "open an app",
    "music_control": "play some music",
    "file_ops": "work with files",
    "system_info": "check system status",
}


# ── Logging helpers ───────────────────────────────────────────────────────────

async def log_tool_call(tool_name: str) -> None:
    await log_usage("tool_call", tool_name)


async def log_app_launch(app_name: str) -> None:
    await log_usage("app_launch", app_name)


async def log_voice_trigger(trigger_type: str) -> None:
    await log_usage("voice_wake", trigger_type)


# ── Proactive suggestion ──────────────────────────────────────────────────────

async def get_proactive_suggestion() -> str | None:
    """
    Analyze usage patterns for the current hour.
    Return a suggestion string if a strong pattern exists, else None.
    """
    now = datetime.now()
    hour = now.hour

    # Check most common tool at this hour
    tool_stats = await get_usage_stats("tool_call", hour, window=1)
    if tool_stats and tool_stats[0]["count"] >= SUGGESTION_THRESHOLD:
        top_tool = tool_stats[0]["detail"]
        label = _TOOL_LABELS.get(top_tool, top_tool.replace("_", " "))
        return f"Chester often {label} around {_hour_label(hour)}."

    # Check most launched app at this hour
    app_stats = await get_usage_stats("app_launch", hour, window=1)
    if app_stats and app_stats[0]["count"] >= SUGGESTION_THRESHOLD:
        app = app_stats[0]["detail"]
        return f"Chester usually opens {app.capitalize()} around {_hour_label(hour)}."

    return None


def _hour_label(hour: int) -> str:
    if hour == 0:
        return "midnight"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "noon"
    return f"{hour - 12} PM"
