"""Build dynamic system prompt and conversation context for LLM calls."""

import yaml
from alice.brain.llm.base import Message
from alice.config import settings
from alice.memory.store import get_all_preferences, get_history


def _load_system_prompt() -> str:
    with open(settings.persona_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"].strip()


async def build_messages(
    session_id: str,
    user_input: str,
    language: str = "en",
    extra_context: str | None = None,
) -> list[Message]:
    """
    Assemble the full message list for an LLM call:
    [system] + [history] + [user]
    """
    base_prompt = _load_system_prompt()

    # Inject preferences into system prompt
    preferences = await get_all_preferences()
    pref_block = ""
    if preferences:
        pref_lines = "\n".join(f"- {k}: {v}" for k, v in preferences.items())
        pref_block = f"\n\n## Chester's Known Preferences\n{pref_lines}"

    # Language instruction
    lang_instruction = ""
    if language == "ja":
        lang_instruction = (
            "\n\n## Language Mode: Japanese\n"
            "Respond in Japanese. Also provide an English translation below your "
            "Japanese response, prefixed with [EN]:"
        )

    if extra_context:
        extra_block = f"\n\n## Current Context\n{extra_context}"
    else:
        extra_block = ""

    system_content = base_prompt + pref_block + lang_instruction + extra_block
    messages: list[Message] = [Message(role="system", content=system_content)]

    # Historical messages
    history = await get_history(session_id)
    for entry in history:
        messages.append(Message(role=entry["role"], content=entry["content"]))

    # Current user message
    messages.append(Message(role="user", content=user_input))
    return messages
