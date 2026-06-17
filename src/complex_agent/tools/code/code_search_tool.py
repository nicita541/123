from __future__ import annotations

from complex_agent.tools.filesystem.search_files_tool import SearchFilesTool


class CodeSearchTool(SearchFilesTool):
    name = "code_search"
    description = "Search source code."

