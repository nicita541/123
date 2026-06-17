from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool is already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def list_tools(self) -> list[str]:
        return sorted(name for name, tool in self._tools.items() if tool.availability == "enabled")

    def list_tool_info(self, *, include_all: bool = True) -> list[dict[str, str]]:
        tools = self._tools.items() if include_all else (
            (name, tool) for name, tool in self._tools.items() if tool.availability == "enabled"
        )
        return [
            {
                "name": name,
                "status": tool.availability,
                "description": tool.description,
            }
            for name, tool in sorted(tools)
        ]

    def run(self, name: str, data: dict[str, object], context: ToolContext) -> ToolResult:
        tool = self.get(name)
        tool.validate_input(data)
        return tool.run(data, context)
