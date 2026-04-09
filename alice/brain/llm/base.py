from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str | None = None  # None allowed for assistant messages with tool_calls
    tool_call_id: str | None = None  # required when role="tool"
    tool_calls: list["ToolCall"] | None = None  # set on assistant messages that invoke tools


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMChunk:
    content: str
    done: bool
    tool_calls: list[ToolCall] | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Stream a response, yielding LLMChunk objects."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMChunk:
        """Return a single complete response (non-streaming)."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable."""
        ...
