import json
from collections.abc import AsyncGenerator

import httpx
from alice.brain.llm.base import LLMChunk, LLMProvider, Message, RateLimitError, ToolCall
from alice.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            msg: dict = {"role": m.role}

            # content: null for assistant+tool_calls (Groq requirement), string otherwise
            if m.tool_calls:
                msg["content"] = m.content  # may be None/null
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
        payload: dict = {
            "model": self._model,
            "messages": self._format_messages(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                GROQ_API_URL,
                headers=self._build_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        yield LLMChunk(content="", done=True)
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content = delta.get("content") or ""
                    finish = choice.get("finish_reason")

                    # Handle tool calls in streaming (accumulate)
                    tool_calls_raw = delta.get("tool_calls")
                    if tool_calls_raw:
                        # Tool calls come fragmented — yield after finish
                        continue

                    yield LLMChunk(content=content, done=finish == "stop")

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
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
                    headers=self._build_headers(),
                    json=payload,
                )
                # Groq 400 tool_use_failed — model mangled the tool call generation.
                # Retry once without tools so Alice can still answer.
                if response.status_code == 400 and tools:
                    body = response.json()
                    err = body.get("error", {})
                    if err.get("code") == "tool_use_failed":
                        import logging as _logging
                        _logging.getLogger(__name__).warning(
                            "Groq tool_use_failed — retrying without tools"
                        )
                        fallback = {k: v for k, v in payload.items()
                                    if k not in ("tools", "tool_choice")}
                        response = await client.post(
                            GROQ_API_URL,
                            headers=self._build_headers(),
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
                raise RateLimitError("Groq rate limit hit — switching to next provider.")
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
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers=self._build_headers(),
                )
                return response.status_code == 200
        except Exception:
            return False
