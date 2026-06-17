from __future__ import annotations

import tempfile
import unittest

from complex_agent.context.context_builder import ContextBuilder
from complex_agent.core.modes import AgentMode
from complex_agent.core.task import Task


class ContextBuilderTests(unittest.TestCase):
    def test_initial_context_contains_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            task = Task.create("Hello", mode=AgentMode.PLAN, project_path=temp)
            context = ContextBuilder().build_initial_context(task)
            self.assertEqual(context.items[0].content, "Hello")


if __name__ == "__main__":
    unittest.main()

