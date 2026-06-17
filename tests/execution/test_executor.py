from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from complex_agent.app import AgentRuntime
from complex_agent.core.modes import AgentMode


class ExecutorTests(unittest.TestCase):
    def test_audit_run_completes_without_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("# TODO: demo\n", encoding="utf-8")
            runtime = AgentRuntime(project_path=root)
            state = runtime.run("Audit this project", mode=AgentMode.AUDIT)
            self.assertTrue(state.final_result)
            self.assertTrue(state.final_result.success, state.errors)


if __name__ == "__main__":
    unittest.main()

