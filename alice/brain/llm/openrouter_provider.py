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
        self._api_key = settings.openrouter_api_key
        self._model = settings.openrouter_model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
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
        payload: dict = {
            "model": self._model,
            "messages": self._format_messages(messages),
        }
        # Note: free OpenRouter models may not support tool calling.
        # Omit tools to avoid errors; Alice will respond in text only via this provider.
        # (Tool results already injected into messages by the engine before this call.)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(OPENROUTER_API_URL, headers=self._headers(), json=payload)
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
                raise RateLimitError("OpenRouter rate limit hit — switching to next provider.")
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
                tool_calls = None  # ignore malformed tool calls from free models

        return LLMChunk(content=content, done=True, tool_calls=tool_calls)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        result = await self.complete(messages, tools)
        yield result

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=self._headers(),
                )
                return r.status_code == 200
        except Exception:
            return False
