from __future__ import annotations

import tempfile
import unittest

from complex_agent.context.context_builder import ContextBuilder
from complex_agent.core.modes import AgentMode
from complex_agent.core.task import Task
from complex_agent.planning.plan_validator import PlanValidator
from complex_agent.planning.planner import Planner


class PlannerTests(unittest.TestCase):
    def test_creates_auditable_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            task = Task.create("Audit this project", mode=AgentMode.AUDIT, project_path=temp)
            context = ContextBuilder().build_initial_context(task)
            plan = Planner().create_plan(task, context)
            PlanValidator().validate(plan)
            tools = [step.required_tool for step in plan.steps]
            self.assertIn("project_scan", tools)
            self.assertIn("final_report", tools)


if __name__ == "__main__":
    unittest.main()

