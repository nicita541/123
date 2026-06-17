from __future__ import annotations

import tempfile
import unittest

from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.shell.shell_tool import ShellTool


class ShellToolTests(unittest.TestCase):
    def test_shell_blocks_unallowlisted_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = ShellTool().run({"command": "echo hello"}, ToolContext(__import__("pathlib").Path(temp), SafetyPolicy(temp)))
            self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()

