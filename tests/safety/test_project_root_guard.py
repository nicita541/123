from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from complex_agent.safety.project_root_guard import ProjectRootGuard


class ProjectRootGuardTests(unittest.TestCase):
    def test_rejects_filesystem_root_and_home(self) -> None:
        guard = ProjectRootGuard()
        self.assertFalse(guard.evaluate(Path.cwd().anchor).allowed)
        self.assertFalse(guard.evaluate(Path.home()).allowed)

    def test_allows_specific_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(ProjectRootGuard().evaluate(temp).allowed)


if __name__ == "__main__":
    unittest.main()
