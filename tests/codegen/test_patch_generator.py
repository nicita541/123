from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from complex_agent.codegen.patch_generator import PatchGenerator
from complex_agent.core.modes import AgentMode
from complex_agent.core.task import Task
from complex_agent.safety.safety_policy import SafetyPolicy


class FakeOllamaProvider:
    def __init__(self, text: str) -> None:
        self.text = text
        self.model = "qwen3-coder:30b"

    def select_available_model(self) -> list[str]:
        return ["qwen3-coder:30b"]

    def complete(self, prompt: str) -> str:
        return self.text

    def complete_structured(self, prompt: str, schema_hint=None):  # type: ignore[no-untyped-def]
        return {
            "goal": "Create a file",
            "summary": "Create one safe file.",
            "steps": [
                {
                    "title": "Patch",
                    "description": "Create a file",
                    "tool": "apply_patch",
                    "risk": "high",
                    "requires_approval": True,
                }
            ],
            "expected_files": ["snake.py"],
            "verification": ["python -m py_compile snake.py"],
        }


class PatchGeneratorTests(unittest.TestCase):
    def test_calculator_skill_only_recognized_when_demo_fallback_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            diff = "--- /dev/null\n+++ b/calculator.py\n@@ -0,0 +1 @@\n+print('ollama')\n"
            default_generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(diff),  # type: ignore[arg-type]
            )
            demo_generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(diff),  # type: ignore[arg-type]
                allow_demo_fallback=True,
            )
            self.assertFalse(default_generator.supports("Создай консольный калькулятор на Python"))
            self.assertTrue(demo_generator.supports("Создай консольный калькулятор на Python"))

    def test_calculator_demo_fallback_creates_plan_and_patch_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generator = PatchGenerator(SafetyPolicy(root), allow_demo_fallback=True)
            task = Task.create("Создай калькулятор на Python", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root, plan=plan)
            self.assertTrue(plan.steps)
            self.assertEqual(proposal.skill_name, "python_calculator")
            self.assertIn("calculator.py", proposal.changed_files)
            self.assertIn("+++ b/calculator.py", proposal.patch)
            self.assertIn("--self-test", proposal.patch)

    def test_ollama_first_even_for_calculator_like_task_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            diff = "--- /dev/null\n+++ b/calculator.py\n@@ -0,0 +1 @@\n+print('from ollama')\n"
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(diff),  # type: ignore[arg-type]
            )
            task = Task.create("Создай калькулятор на Python", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root, plan=plan)
            self.assertEqual(proposal.skill_name, "ollama")
            self.assertIn("calculator.py", proposal.changed_files)
            self.assertFalse((root / "calculator.py").exists())

    def test_forbidden_file_patch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            generator = PatchGenerator(SafetyPolicy(temp), allow_demo_fallback=True)
            patch = "--- /dev/null\n+++ b/.env\n@@ -0,0 +1 @@\n+token=abc\n"
            with self.assertRaises(ValueError):
                generator.validate_patch(patch)

    def test_valid_ollama_diff_is_accepted_without_deterministic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            diff = (
                "--- /dev/null\n"
                "+++ b/snake.py\n"
                "@@ -0,0 +1,2 @@\n"
                "+print('snake')\n"
                "+\n"
            )
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(diff),  # type: ignore[arg-type]
            )
            task = Task.create("Создай snake.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root, plan=plan)
            self.assertEqual(proposal.skill_name, "ollama")
            self.assertEqual(proposal.changed_files, ["snake.py"])
            self.assertFalse((root / "snake.py").exists())

    def test_bad_ollama_diff_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider("not a diff"),  # type: ignore[arg-type]
            )
            task = Task.create("Сделай новую функцию", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            with self.assertRaises(Exception):
                generator.propose(task, root, plan=plan)

    def test_markdown_fenced_ollama_diff_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fenced = "```diff\n--- /dev/null\n+++ b/snake.py\n@@ -0,0 +1 @@\n+print('x')\n```"
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(fenced),  # type: ignore[arg-type]
            )
            task = Task.create("Создай snake.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            with self.assertRaises(Exception):
                generator.propose(task, root, plan=plan)


if __name__ == "__main__":
    unittest.main()
