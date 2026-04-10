import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx
from alice.brain.llm.base import LLMChunk, LLMProvider, Message, RateLimitError, ToolCall
from alice.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
KEY_COOLDOWN_SECONDS = 120.0

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        import os
        # Numbered keys: GROQ_API_KEY_1, GROQ_API_KEY_2, ... (preferred, easy to read)
        numbered = []
        i = 1
        while True:
            key = os.environ.get(f"GROQ_API_KEY_{i}", "").strip()
            if not key:
                break
            numbered.append(key)
            i += 1

        # Fallback: comma-separated GROQ_API_KEY (legacy / single key)
        base = [k.strip() for k in settings.groq_api_key.split(",") if k.strip()]

        # Numbered takes priority; merge without duplicates
        seen = set(numbered)
        for k in base:
            if k not in seen:
                numbered.append(k)
                seen.add(k)

        self._keys: list[str] = numbered
        self._model = settings.groq_model
        self._limited_until: dict[int, float] = {}  # key index → monotonic time

        logger.info("Groq: %d API key(s) loaded — rotating on rate limit", len(self._keys))

    def _available_keys(self) -> list[tuple[int, str]]:
        now = time.monotonic()
        return [
            (i, key)
            for i, key in enumerate(self._keys)
            if now >= self._limited_until.get(i, 0.0)
        ]

    def _mark_key_limited(self, idx: int) -> None:
        self._limited_until[idx] = time.monotonic() + KEY_COOLDOWN_SECONDS
        available = len(self._available_keys())
        logger.warning(
            "Groq key #%d rate-limited — cooling %ds. %d/%d keys still available.",
            idx, int(KEY_COOLDOWN_SECONDS), available, len(self._keys),
        )

    def _headers(self, key: str) -> dict:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
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
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            else:
                msg["content"] = m.content or ""
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            result.append(msg)
        return result

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        # stream() delegates to complete() for simplicity (key rotation logic lives there)
        result = await self.complete(messages, tools)
        yield result

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMChunk:
        available = self._available_keys()
        if not available:
            # All keys cooling — try all anyway as last resort before giving up
            logger.warning("All Groq keys cooling down — trying all anyway")
            available = list(enumerate(self._keys))

        last_exc: Exception = RateLimitError("All Groq keys rate-limited.")

        for idx, key in available:
            try:
                return await self._complete_with_key(key, messages, tools)
            except RateLimitError:
                self._mark_key_limited(idx)
                last_exc = RateLimitError("All Groq keys rate-limited.")
            except RuntimeError as exc:
                raise  # non-rate-limit errors bubble up immediately

        raise last_exc  # all keys exhausted → FallbackRouter tries next provider

    async def _complete_with_key(
        self,
        key: str,
        messages: list[Message],
        tools: list[dict] | None,
    ) -> LLMChunk:
        payload: dict = {
            "model": self._model,
            "messages": self._format_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers=self._headers(key),
                    json=payload,
                )
                # Groq 400 tool_use_failed — retry without tools
                if response.status_code == 400 and tools:
                    body = response.json()
                    if body.get("error", {}).get("code") == "tool_use_failed":
                        logger.warning("Groq tool_use_failed — retrying without tools")
                        fallback = {k: v for k, v in payload.items()
                                    if k not in ("tools", "tool_choice")}
                        response = await client.post(
                            GROQ_API_URL,
                            headers=self._headers(key),
                            json=fallback,
                        )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError:
            raise RuntimeError("Cannot reach Groq API — check internet connection.")
        except httpx.TimeoutException:
            raise RuntimeError("Groq API timed out — try again.")
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                raise RuntimeError("Groq API key invalid — check GROQ_API_KEY in .env.")
            if code == 429:
                logger.warning("Groq 429: %s", exc.response.text[:300])
                raise RateLimitError("Groq key rate-limited.")
            raise RuntimeError(f"Groq API error {code}: {exc.response.text[:200]}")

        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        tool_calls = None

        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                )
                for tc in raw_tool_calls
            ]

        return LLMChunk(content=content, done=True, tool_calls=tool_calls)

    async def health_check(self) -> bool:
        available = self._available_keys()
        if not available:
            return False
        _, key = available[0]
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers=self._headers(key),
                )
                return r.status_code == 200
        except Exception:
            return False
