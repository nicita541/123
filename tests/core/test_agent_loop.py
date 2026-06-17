from __future__ import annotations

import tempfile
import unittest

from complex_agent.core.agent_loop import AgentLoop
from complex_agent.core.modes import AgentMode


class AgentLoopTests(unittest.TestCase):
    def test_agent_loop_plans(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            loop = AgentLoop(project_path=temp)
            plan = loop.plan("Audit", mode=AgentMode.PLAN)
            self.assertGreaterEqual(len(plan.steps), 1)


if __name__ == "__main__":
    unittest.main()

