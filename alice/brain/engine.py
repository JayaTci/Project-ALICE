"""Core brain — receives text input, calls LLM, handles tools, returns response."""

import json
import logging
from collections.abc import AsyncGenerator

from alice.brain.llm.base import LLMChunk, Message
from alice.brain.llm.router import get_provider
from alice.memory.context import build_messages
from alice.memory.store import save_message

logger = logging.getLogger(__name__)

# Max tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5


class AliceBrain:
    def __init__(self, session_id: str, language: str = "en") -> None:
        self.session_id = session_id
        # Seed global language manager with provided default
        from alice.brain.language import set_language, get_language
        if language != "en":
            set_language(language)
        self._provider = get_provider()
        self._tools_enabled = False
        self._tool_schemas: list[dict] = []

    @property
    def language(self) -> str:
        from alice.brain.language import get_language
        return get_language()

    def enable_tools(self) -> None:
        """Register tools for LLM function calling."""
        from alice.tools.base import register_all_tools, all_schemas
        register_all_tools()
        self._tool_schemas = all_schemas()
        self._tools_enabled = True
        logger.info("Tools enabled: %d registered", len(self._tool_schemas))

    async def respond_stream(
        self,
        user_input: str,
        extra_context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Save user message → detect language → call LLM (with tools if enabled) →
        execute any tool calls → yield streamed final response.
        """
        from alice.brain.language import (
            is_language_command, set_language, update_from_input, get_language,
        )

        # ── Language command shortcut ─────────────────────────────────────
        lang_cmd = is_language_command(user_input)
        if lang_cmd is not None:
            set_language(lang_cmd)
            if lang_cmd == "ja":
                reply = "はい、日本語で話します。何でもどうぞ！\n\n[EN: Sure, I'll speak in Japanese. What can I do for you?]"
            else:
                reply = "Switched to English. How can I help you?"
            yield reply
            await save_message(self.session_id, "user", user_input)
            await save_message(self.session_id, "assistant", reply)
            return

        # ── /remember command ─────────────────────────────────────────────
        stripped = user_input.strip()
        if stripped.lower().startswith("/remember "):
            from alice.memory.preferences import handle_remember
            reply = await handle_remember(stripped[10:])
            yield reply
            await save_message(self.session_id, "user", user_input)
            await save_message(self.session_id, "assistant", reply)
            return

        # ── /forget command ───────────────────────────────────────────────
        if stripped.lower().startswith("/forget "):
            from alice.memory.preferences import handle_forget
            reply = await handle_forget(stripped[8:])
            yield reply
            await save_message(self.session_id, "user", user_input)
            await save_message(self.session_id, "assistant", reply)
            return

        # ── /memories command ─────────────────────────────────────────────
        if stripped.lower() in {"/memories", "/memory", "/remember"}:
            from alice.memory.preferences import list_memories
            reply = await list_memories()
            yield reply
            await save_message(self.session_id, "user", user_input)
            await save_message(self.session_id, "assistant", reply)
            return

        # ── Auto-detect language from input ───────────────────────────────
        current_lang = update_from_input(user_input)
        logger.debug("Language: %s", current_lang)

        # ── Schedule background preference extraction ──────────────────────
        from alice.memory.preferences import schedule_extraction
        schedule_extraction(user_input)

        await save_message(self.session_id, "user", user_input)

        messages = await build_messages(
            self.session_id,
            user_input,
            language=current_lang,
            extra_context=extra_context,
        )

        tools = self._tool_schemas if self._tools_enabled else None

        # Tool execution loop
        for _round in range(MAX_TOOL_ROUNDS):
            result = await self._provider.complete(messages, tools=tools)

            # No tool calls → stream the content response
            if not result.tool_calls:
                full_response = result.content
                if full_response:
                    # Yield in chunks for streaming feel
                    chunk_size = 10
                    for i in range(0, len(full_response), chunk_size):
                        yield full_response[i:i + chunk_size]
                    await save_message(self.session_id, "assistant", full_response)
                return

            # Handle tool calls
            if result.content:
                yield result.content  # May have pre-tool commentary

            # Append assistant turn with tool calls to message history
            # content must be None (not "") when tool_calls present — Groq requirement
            messages.append(Message(
                role="assistant",
                content=result.content if result.content else None,
                tool_calls=result.tool_calls,
            ))

            # Execute each tool and append results as "tool" role messages
            from alice.tools.base import execute_tool
            from alice.memory.patterns import log_tool_call
            for tc in result.tool_calls:
                logger.info("Executing tool: %s(%s)", tc.name, tc.arguments)
                yield f"\n[Executing: {tc.name}...]\n"

                tool_result = await execute_tool(tc.name, **tc.arguments)
                tool_output = tool_result.output if tool_result.success else f"Error: {tool_result.error}"

                # Log for pattern analysis (fire-and-forget)
                import asyncio as _asyncio
                _asyncio.create_task(log_tool_call(tc.name))

                messages.append(Message(
                    role="tool",
                    content=tool_output,
                    tool_call_id=tc.id,
                ))

        logger.warning("Reached max tool rounds (%d)", MAX_TOOL_ROUNDS)

    async def respond(
        self,
        user_input: str,
        extra_context: str | None = None,
    ) -> str:
        """Non-streaming — collect and return full text."""
        full = ""
        async for chunk in self.respond_stream(user_input, extra_context):
            full += chunk
        return full
