"""
OpenRouter provider — OpenAI-compatible gateway to many free models.
Free models (no cost, rate-limited):
  - meta-llama/llama-3.3-70b-instruct:free
  - google/gemma-3-27b-it:free
  - mistralai/mistral-7b-instruct:free
Get API key free at: https://openrouter.ai
"""

import json
from collections.abc import AsyncGenerator

import httpx
from alice.brain.llm.base import LLMChunk, LLMProvider, Message, RateLimitError, ToolCall
from alice.config import settings

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(LLMProvider):
    def __init__(self) -> None:
        import os
        import time as _time

        # Numbered keys: OPENROUTER_API_KEY_1, OPENROUTER_API_KEY_2, ...
        numbered = []
        i = 1
        while True:
            key = os.environ.get(f"OPENROUTER_API_KEY_{i}", "").strip()
            if not key:
                break
            numbered.append(key)
            i += 1

        # Fallback: single OPENROUTER_API_KEY
        base = settings.openrouter_api_key.strip()
        if base and base not in numbered:
            numbered.append(base)

        self._keys: list[str] = numbered
        self._key_index: int = 0
        self._limited_until: dict[int, float] = {}
        self._model = settings.openrouter_model

        import logging as _log
        _log.getLogger(__name__).info(
            "OpenRouter: %d API key(s) loaded", len(self._keys)
        )

    def _next_key(self) -> str | None:
        import time
        now = time.monotonic()
        for i, key in enumerate(self._keys):
            if now >= self._limited_until.get(i, 0.0):
                return key
        return None

    def _mark_limited(self, key: str) -> None:
        import time, logging as _log
        for i, k in enumerate(self._keys):
            if k == key:
                self._limited_until[i] = time.monotonic() + 120.0
                available = sum(
                    1 for j in range(len(self._keys))
                    if time.monotonic() >= self._limited_until.get(j, 0.0)
                )
                _log.getLogger(__name__).warning(
                    "OpenRouter key #%d rate-limited. %d/%d keys available.",
                    i, available, len(self._keys)
                )
                break

    def _headers(self, key: str) -> dict:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8765",
            "X-Title": "Alice AI Assistant",
        }

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            msg: dict = {"role": m.role}
            if m.tool_calls:
                msg["content"] = m.content
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m.tool_calls
                ]
            else:
                msg["content"] = m.content or ""
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            result.append(msg)
        return result

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMChunk:
        import time
        # Try each available key in order
        available = [
            (i, k) for i, k in enumerate(self._keys)
            if time.monotonic() >= self._limited_until.get(i, 0.0)
        ]
        if not available:
            available = list(enumerate(self._keys))  # all cooling — try anyway

        last_exc: Exception = RateLimitError("All OpenRouter keys rate-limited.")

        for idx, key in available:
            try:
                return await self._complete_with_key(key, messages)
            except RateLimitError:
                self._mark_limited(key)
                last_exc = RateLimitError("All OpenRouter keys rate-limited.")
            except RuntimeError:
                raise

        raise last_exc

    async def _complete_with_key(
        self,
        key: str,
        messages: list[Message],
    ) -> LLMChunk:
        payload: dict = {
            "model": self._model,
            "messages": self._format_messages(messages),
        }
        # Free OpenRouter models may not support tool calling — omit tools.

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    OPENROUTER_API_URL, headers=self._headers(key), json=payload
                )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError:
            raise RuntimeError("Cannot reach OpenRouter API — check internet connection.")
        except httpx.TimeoutException:
            raise RuntimeError("OpenRouter API timed out.")
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                raise RuntimeError("OpenRouter API key invalid — check OPENROUTER_API_KEY in .env.")
            if code == 429:
                import logging as _log
                _log.getLogger(__name__).warning("OpenRouter 429: %s", exc.response.text[:300])
                raise RateLimitError("OpenRouter key rate-limited.")
            raise RuntimeError(f"OpenRouter API error {code}: {exc.response.text[:200]}")

        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""

        raw_tool_calls = message.get("tool_calls")
        tool_calls = None
        if raw_tool_calls:
            try:
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"]),
                    )
                    for tc in raw_tool_calls
                ]
            except Exception:
                tool_calls = None

        return LLMChunk(content=content, done=True, tool_calls=tool_calls)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        result = await self.complete(messages, tools)
        yield result

    async def health_check(self) -> bool:
        key = self._next_key()
        if not key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=self._headers(key),
                )
                return r.status_code == 200
        except Exception:
            return False
