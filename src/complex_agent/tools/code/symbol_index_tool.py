from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class SymbolIndexTool(BaseTool):
    name = "symbol_index"
    description = "Placeholder symbol indexer for future AST/LSP integration."

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult(True, "", summary="Symbol indexing is not implemented in MVP.")

