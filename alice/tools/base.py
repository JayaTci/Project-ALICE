"""Tool base class and registry for Alice's tool system."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, "BaseTool"] = {}


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""


class BaseTool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema object for LLM function calling
    is_read_only: bool = True
    requires_confirmation: bool = False

    def to_llm_schema(self) -> dict:
        """Return Groq/OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...


def register(tool: BaseTool) -> None:
    _REGISTRY[tool.name] = tool
    logger.debug("Tool registered: %s", tool.name)


def get_tool(name: str) -> BaseTool | None:
    return _REGISTRY.get(name)


def all_tools() -> list[BaseTool]:
    return list(_REGISTRY.values())


def all_schemas() -> list[dict]:
    """Return all tool schemas for LLM function calling."""
    return [t.to_llm_schema() for t in _REGISTRY.values()]


async def execute_tool(name: str, **kwargs) -> ToolResult:
    tool = _REGISTRY.get(name)
    if tool is None:
        return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
    try:
        return await tool.execute(**kwargs)
    except Exception as exc:
        logger.exception("Tool '%s' raised exception", name)
        return ToolResult(success=False, output="", error=str(exc))


def register_all_tools() -> None:
    """Import and register all available tools."""
    from alice.tools.system_info import SystemInfoTool
    from alice.tools.pc_control import PCControlTool
    from alice.tools.file_ops import FileOpsTool
    from alice.tools.weather import WeatherTool
    from alice.tools.news import NewsTool
    from alice.tools.music import MusicTool
    from alice.tools.apps import AppsTool

    for tool in [
        SystemInfoTool(),
        PCControlTool(),
        FileOpsTool(),
        WeatherTool(),
        NewsTool(),
        MusicTool(),
        AppsTool(),
    ]:
        register(tool)

    logger.info("Registered %d tools", len(_REGISTRY))
