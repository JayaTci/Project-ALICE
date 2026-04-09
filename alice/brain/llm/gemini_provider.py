"""
Google Gemini provider — uses Google's OpenAI-compatible endpoint.
Free tier: 15 RPM / 1M tokens/day on gemini-2.0-flash.
Get API key free at: https://aistudio.google.com/apikey
"""

import json
from collections.abc import AsyncGenerator

import httpx
from alice.brain.llm.base import LLMChunk, LLMProvider, Message, RateLimitError, ToolCall
from alice.config import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
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
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(GEMINI_API_URL, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError:
            raise RuntimeError("Cannot reach Gemini API — check internet connection.")
        except httpx.TimeoutException:
            raise RuntimeError("Gemini API timed out.")
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                raise RuntimeError("Gemini API key invalid — check GEMINI_API_KEY in .env.")
            if code == 429:
                raise RateLimitError("Gemini rate limit hit — switching to next provider.")
            raise RuntimeError(f"Gemini API error {code}: {exc.response.text[:200]}")

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
                    "https://generativelanguage.googleapis.com/v1beta/openai/models",
                    headers=self._headers(),
                )
                return r.status_code == 200
        except Exception:
            return False
