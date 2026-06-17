from __future__ import annotations

from complex_agent.review.final_report_builder import FinalReportTool
from complex_agent.tools.code.code_search_tool import CodeSearchTool
from complex_agent.tools.code.lint_tool import LintTool
from complex_agent.tools.code.test_runner_tool import TestRunnerTool
from complex_agent.tools.filesystem.diff_tool import DiffTool
from complex_agent.tools.filesystem.list_files_tool import ListFilesTool
from complex_agent.tools.filesystem.patch_tool import ApplyPatchTool
from complex_agent.tools.filesystem.read_file_tool import ReadFileTool
from complex_agent.tools.filesystem.search_files_tool import SearchFilesTool
from complex_agent.tools.git.git_branch_tool import GitBranchTool
from complex_agent.tools.git.git_commit_tool import GitCommitTool
from complex_agent.tools.git.git_diff_tool import GitDiffTool
from complex_agent.tools.git.git_status_tool import GitStatusTool
from complex_agent.tools.project.build_tool import BuildTool
from complex_agent.tools.project.dependency_tool import DependencyTool
from complex_agent.tools.project.diagnostics_tool import DiagnosticsTool
from complex_agent.tools.project.project_scan_tool import ProjectScanTool
from complex_agent.tools.registry import ToolRegistry
from complex_agent.tools.shell.shell_tool import ShellTool


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in [
        ListFilesTool(),
        ReadFileTool(),
        SearchFilesTool(),
        DiffTool(),
        ApplyPatchTool(),
        ShellTool(),
        GitStatusTool(),
        GitDiffTool(),
        GitBranchTool(),
        GitCommitTool(),
        ProjectScanTool(),
        DependencyTool(),
        BuildTool(),
        DiagnosticsTool(),
        CodeSearchTool(),
        LintTool(),
        TestRunnerTool(),
        FinalReportTool(),
    ]:
        registry.register(tool)
    return registry

