from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from complex_agent.codegen.patch_generator import PatchGenerator
from complex_agent.core.modes import AgentMode
from complex_agent.core.task import Task
from complex_agent.safety.safety_policy import SafetyPolicy


class PatchGeneratorTests(unittest.TestCase):
    def test_calculator_skill_recognizes_russian_and_english_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            generator = PatchGenerator(SafetyPolicy(temp))
            self.assertTrue(generator.supports("Сделай консольный калькулятор на Python"))
            self.assertTrue(generator.supports("Create a python calculator"))

    def test_calculator_skill_creates_plan_and_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generator = PatchGenerator(SafetyPolicy(root))
            task = Task.create("Сделай калькулятор на Python", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root)
            self.assertTrue(plan.steps)
            self.assertIn("calculator.py", proposal.changed_files)
            self.assertIn("+++ b/calculator.py", proposal.patch)
            self.assertIn("--self-test", proposal.patch)

    def test_propose_does_not_apply_patch_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generator = PatchGenerator(SafetyPolicy(root))
            task = Task.create("Сделай калькулятор на Python", mode=AgentMode.REVIEW, project_path=root)
            generator.propose(task, root)
            self.assertFalse((root / "calculator.py").exists())

    def test_forbidden_file_patch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            generator = PatchGenerator(SafetyPolicy(temp))
            patch = "--- /dev/null\n+++ b/.env\n@@ -0,0 +1 @@\n+token=abc\n"
            with self.assertRaises(ValueError):
                generator.validate_patch(patch)


if __name__ == "__main__":
    unittest.main()
