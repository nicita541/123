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


class SequentialOllamaProvider(FakeOllamaProvider):
    def __init__(self, texts: list[str]) -> None:
        super().__init__(texts[-1])
        self.texts = iter(texts)

    def complete(self, prompt: str) -> str:
        return next(self.texts)


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
            task = Task.create(
                "Создай калькулятор на Python", mode=AgentMode.REVIEW, project_path=root
            )
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
            task = Task.create(
                "Создай калькулятор на Python", mode=AgentMode.REVIEW, project_path=root
            )
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
            diff = "--- /dev/null\n+++ b/snake.py\n@@ -0,0 +1,2 @@\n+print('snake')\n+\n"
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

    def test_single_markdown_fenced_ollama_diff_is_unwrapped_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fenced = "```diff\n--- /dev/null\n+++ b/snake.py\n@@ -0,0 +1 @@\n+print('x')\n```"
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(fenced),  # type: ignore[arg-type]
            )
            task = Task.create("Создай snake.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root, plan=plan)
            self.assertEqual(proposal.changed_files, ["snake.py"])
            self.assertTrue(proposal.patch.startswith("--- /dev/null"))

    def test_markdown_explanation_around_single_fenced_diff_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fenced = (
                "Here is the patch:\n```diff\n--- /dev/null\n+++ b/snake.py\n"
                "@@ -0,0 +1 @@\n+print('x')\n```"
            )
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(fenced),  # type: ignore[arg-type]
            )
            task = Task.create("Create snake.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root, plan=plan)
            self.assertEqual(proposal.changed_files, ["snake.py"])

    def test_multiple_markdown_fences_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fenced = (
                "```diff\n--- /dev/null\n+++ b/snake.py\n@@ -0,0 +1 @@\n+print('x')\n```\n"
                "```text\nextra\n```"
            )
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=FakeOllamaProvider(fenced),  # type: ignore[arg-type]
            )
            task = Task.create("Create snake.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            with self.assertRaises(Exception):
                generator.propose(task, root, plan=plan)

    def test_context_mismatched_diff_is_retried_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("before\n", encoding="utf-8")
            invalid = "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-nope\n+after\n"
            valid = "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-before\n+after\n"
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=SequentialOllamaProvider([invalid, valid]),  # type: ignore[arg-type]
            )
            task = Task.create("Update sample.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            proposal = generator.propose(task, root, plan=plan)
            self.assertEqual(proposal.patch, valid)
            self.assertEqual((root / "sample.py").read_text(encoding="utf-8"), "before\n")

    def test_expected_plan_path_is_required_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wrong = "--- /dev/null\n+++ b/todolist.py\n@@ -0,0 +1 @@\n+print('wrong')\n"
            valid = "--- /dev/null\n+++ b/todo.py\n@@ -0,0 +1 @@\n+print('right')\n"
            generator = PatchGenerator(
                SafetyPolicy(root),
                ollama_provider=SequentialOllamaProvider([wrong, valid]),  # type: ignore[arg-type]
            )
            task = Task.create("Create todo.py", mode=AgentMode.REVIEW, project_path=root)
            plan = generator.create_plan(task)
            plan.risks.clear()
            plan.risks.append(f"Expected files: {root / 'todo.py'}")

            proposal = generator.propose(task, root, plan=plan)

            self.assertEqual(proposal.changed_files, ["todo.py"])
            self.assertFalse((root / "todo.py").exists())


if __name__ == "__main__":
    unittest.main()
