from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from complex_agent.api.server import create_app
from complex_agent.codegen.patch_generator import PatchGenerator, ProposedPatch
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep
from complex_agent.tools.base_tool import ToolContext


CALCULATOR_TASK = "Создай консольный калькулятор на Python"
SNAKE_TASK = (
    "Создай snake.py: простая консольная змейка на Python без внешних зависимостей. "
    "Не запускай интерактивную игру, только проверь синтаксис."
)


class ApiTests(unittest.TestCase):
    def test_health_returns_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")

    def test_status_does_not_create_agent_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            response = client.get("/api/status")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("llm_provider", data)
            self.assertIn("ollama_model", data)
            self.assertIn("ollama_reachable", data)
            self.assertIn("ollama_generation_check", data)
            self.assertIn("ollama_models", data)
            self.assertFalse(Path(temp, ".agent").exists())

    def test_status_returns_mocked_ollama_generation_status(self) -> None:
        class FakePatchGenerator:
            def llm_status(self) -> dict[str, object]:
                return {
                    "llm_provider": "ollama",
                    "fallback_provider": "deterministic",
                    "ollama_base_url": "http://127.0.0.1:11434",
                    "ollama_model": "qwen3-coder:30b",
                    "ollama_reachable": True,
                    "ollama_generation_check": True,
                    "ollama_models": ["qwen3-coder:30b", "qwen3:8b"],
                }

        with tempfile.TemporaryDirectory() as temp:
            app = create_app(project_path=temp)
            app.state.session_store.patch_generator = FakePatchGenerator()
            client = TestClient(app)
            data = client.get("/api/status").json()
            self.assertTrue(data["ollama_reachable"])
            self.assertTrue(data["ollama_generation_check"])
            self.assertEqual(data["ollama_model"], "qwen3-coder:30b")
            self.assertEqual(data["ollama_models"], ["qwen3-coder:30b", "qwen3:8b"])

    def test_tools_returns_tool_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            response = client.get("/api/tools")
            self.assertEqual(response.status_code, 200)
            statuses = {tool["name"]: tool["status"] for tool in response.json()["tools"]}
            self.assertNotIn("git_commit", statuses)
            self.assertEqual(statuses["final_report"], "internal")
            self.assertEqual(statuses["read_file"], "enabled")

    def test_project_endpoint_returns_current_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            client = TestClient(create_app(project_path=root))
            response = client.get("/api/project")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["project_root"], str(root))
            self.assertFalse((root / ".agent").exists())

    def test_project_select_valid_path_changes_root_without_agent_state(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            root1 = Path(first).resolve()
            root2 = Path(second).resolve()
            (root2 / "src").mkdir()
            (root2 / "src" / "app.py").write_text("print('selected')\n", encoding="utf-8")
            client = TestClient(create_app(project_path=root1))
            response = client.post("/api/project/select", json={"path": str(root2)})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["project_root"], str(root2))
            self.assertFalse((root1 / ".agent").exists())
            self.assertFalse((root2 / ".agent").exists())
            workspace = client.get("/api/workspace").json()
            self.assertEqual(workspace["project_root"], str(root2))
            self.assertIn("src", workspace["important_directories"])
            files = client.get("/api/files").text
            self.assertIn("src/app.py", files)

    def test_project_select_invalid_path_returns_error_and_keeps_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            missing = root / "missing"
            client = TestClient(create_app(project_path=root))
            response = client.post("/api/project/select", json={"path": str(missing)})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(client.get("/api/project").json()["project_root"], str(root))

    def test_plan_returns_plan_without_mutating_files_or_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("print('ok')\n", encoding="utf-8")
            client = TestClient(create_app(project_path=root))
            response = client.post("/api/tasks/plan", json={"task": "Audit", "mode": "review"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("task_id", data)
            self.assertTrue(data["plan"]["steps"])
            self.assertFalse((root / ".agent").exists())
            self.assertEqual((root / "sample.py").read_text(encoding="utf-8"), "print('ok')\n")

    def test_chat_returns_assistant_response_and_plan_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            client = TestClient(create_app(project_path=root))
            response = client.post(
                "/api/chat",
                json={"message": "Audit this project", "mode": "review"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("assistant_response", data)
            self.assertTrue(data["plan"]["steps"])
            self.assertFalse((root / ".agent").exists())

    def test_forbidden_files_are_not_exposed_through_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env").write_text("SECRET_TOKEN=abc123\n", encoding="utf-8")
            client = TestClient(create_app(project_path=root))
            response = client.post("/api/tasks/plan", json={"task": "Audit SECRET_TOKEN", "mode": "review"})
            self.assertEqual(response.status_code, 200)
            text = response.text
            self.assertNotIn(".env", text)
            self.assertNotIn("abc123", text)

    def test_workspace_and_files_hide_forbidden_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / ".env").write_text("token=abc\n", encoding="utf-8")
            (root / ".agent").mkdir()
            (root / ".agent" / "run.log").write_text("internal\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "hidden.py").write_text("hidden\n", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "cached.pyc").write_text("cached\n", encoding="utf-8")
            (root / "secret").mkdir()
            (root / "secret" / "notes.txt").write_text("secret=abc\n", encoding="utf-8")
            client = TestClient(create_app(project_path=root))
            workspace = client.get("/api/workspace")
            self.assertEqual(workspace.status_code, 200)
            self.assertFalse((root / ".agent" / "runs.sqlite3").exists())
            response = client.get("/api/files")
            self.assertEqual(response.status_code, 200)
            text = response.text
            self.assertIn("src/app.py", text)
            self.assertNotIn(".env", text)
            self.assertNotIn(".agent", text)
            self.assertNotIn(".venv", text)
            self.assertNotIn("__pycache__", text)
            self.assertNotIn("secret/notes.txt", text)

    def test_file_preview_reads_safe_file_redacts_and_blocks_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("token=abc123\nprint('ok')\n", encoding="utf-8")
            (root / ".env").write_text("token=abc123\n", encoding="utf-8")
            client = TestClient(create_app(project_path=root))
            preview = client.get("/api/files/preview", params={"path": "src/app.py"})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["path"], "src/app.py")
            self.assertIn("[REDACTED]", preview.json()["content"])
            self.assertNotIn("abc123", preview.json()["content"])
            blocked = client.get("/api/files/preview", params={"path": ".env"})
            self.assertEqual(blocked.status_code, 403)
            self.assertNotIn("abc123", blocked.text)

    def test_preview_outside_selected_root_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as root_temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(root_temp)
            outside = Path(outside_temp) / "secret.txt"
            outside.write_text("outside\n", encoding="utf-8")
            client = TestClient(create_app(project_path=root))
            response = client.get("/api/files/preview", params={"path": str(outside)})
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("outside", response.text)

    def test_apply_patch_outside_selected_root_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as root_temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(root_temp)
            outside = Path(outside_temp) / "outside.txt"
            app = create_app(project_path=root)
            store = app.state.session_store
            patch_text = f"--- /dev/null\n+++ {outside}\n@@ -0,0 +1 @@\n+bad\n"
            result = store.runtime.registry.run(
                "apply_patch",
                {"patch": patch_text},
                ToolContext(project_root=store.runtime.project_root, safety=store.runtime.safety),
            )
            self.assertFalse(result.success)
            self.assertFalse(outside.exists())

    def test_git_diff_endpoint_is_safe_outside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            response = client.get("/api/git/diff")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["diff"], "")
            self.assertEqual(response.json()["changed_files"], [])

    def test_timeline_returns_ui_events_for_known_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            plan = client.post("/api/tasks/plan", json={"task": "Audit", "mode": "review"})
            self.assertEqual(plan.status_code, 200)
            task_id = plan.json()["task_id"]
            timeline = client.get(f"/api/tasks/{task_id}/timeline")
            self.assertEqual(timeline.status_code, 200)
            data = timeline.json()
            self.assertEqual(data["task_id"], task_id)
            self.assertTrue(data["events"])
            self.assertEqual(client.get("/api/tasks/missing/timeline").status_code, 404)

    def test_calculator_workflow_propose_does_not_create_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = create_app(project_path=root)
            app.state.session_store.patch_generator = PatchGenerator(
                app.state.session_store.runtime.safety,
                allow_demo_fallback=True,
            )
            client = TestClient(app)
            plan = client.post("/api/tasks/plan", json={"task": CALCULATOR_TASK, "mode": "review"})
            self.assertEqual(plan.status_code, 200)
            task_id = plan.json()["task_id"]
            propose = client.post(f"/api/tasks/{task_id}/propose")
            self.assertEqual(propose.status_code, 200)
            data = propose.json()
            self.assertEqual(data["status"], "waiting_approval")
            self.assertIn("calculator.py", data["proposed_files"])
            self.assertIn("+++ b/calculator.py", data["proposed_diff"])
            self.assertTrue(data["pending_approvals"])
            self.assertFalse((root / "calculator.py").exists())

    def test_run_without_approve_does_not_create_calculator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = create_app(project_path=root)
            app.state.session_store.patch_generator = PatchGenerator(
                app.state.session_store.runtime.safety,
                allow_demo_fallback=True,
            )
            client = TestClient(app)
            task_id = client.post(
                "/api/tasks/plan",
                json={"task": CALCULATOR_TASK, "mode": "review"},
            ).json()["task_id"]
            client.post(f"/api/tasks/{task_id}/propose")
            run = client.post(f"/api/tasks/{task_id}/run")
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["status"], "waiting_approval")
            self.assertFalse((root / "calculator.py").exists())

    def test_approve_and_run_creates_calculator_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = create_app(project_path=root)
            app.state.session_store.patch_generator = PatchGenerator(
                app.state.session_store.runtime.safety,
                allow_demo_fallback=True,
            )
            client = TestClient(app)
            task_id = client.post(
                "/api/tasks/plan",
                json={"task": CALCULATOR_TASK, "mode": "review"},
            ).json()["task_id"]
            proposed = client.post(f"/api/tasks/{task_id}/propose").json()
            approval = proposed["pending_approvals"][0]
            approve = client.post(
                f"/api/tasks/{task_id}/approve",
                json={"step_id": approval["step_id"], "action": approval["action"]},
            )
            self.assertEqual(approve.status_code, 200)
            run = client.post(f"/api/tasks/{task_id}/run")
            self.assertEqual(run.status_code, 200)
            data = run.json()
            self.assertEqual(data["status"], "completed")
            self.assertTrue((root / "calculator.py").exists())
            self.assertIn("OK: all calculator self-tests passed", data["verification_output"])
            self.assertIn("python calculator.py --self-test", data["final_report"])
            report = client.get(f"/api/tasks/{task_id}/report")
            self.assertIn("Как запустить", report.json()["report"])

    def test_ollama_snake_workflow_requires_approval_then_py_compile(self) -> None:
        class FakePatchGenerator:
            def llm_status(self) -> dict[str, object]:
                return {
                    "llm_provider": "ollama",
                    "fallback_provider": "deterministic",
                    "ollama_base_url": "http://127.0.0.1:11434",
                    "ollama_model": "qwen3-coder:30b",
                    "ollama_reachable": True,
                    "ollama_generation_check": True,
                    "ollama_models": ["qwen3-coder:30b"],
                }

            def create_plan(self, task):  # type: ignore[no-untyped-def]
                return Plan.create(
                    task_id=task.id,
                    goal=task.normalized_goal,
                    steps=[
                        PlanStep.create(
                            type="patch",
                            description="Create snake.py from an Ollama proposed diff.",
                            required_tool="apply_patch",
                            approval_required=True,
                        ),
                        PlanStep.create(
                            type="verification",
                            description="Compile snake.py.",
                            required_tool="shell",
                            input={"command": "python -m py_compile snake.py"},
                        ),
                    ],
                )

            def propose(self, task, project_root, **kwargs):  # type: ignore[no-untyped-def]
                patch_text = (
                    "--- /dev/null\n"
                    "+++ b/snake.py\n"
                    "@@ -0,0 +1,9 @@\n"
                    "+from __future__ import annotations\n"
                    "+\n"
                    "+\n"
                    "+def main() -> int:\n"
                    "+    print(\"Snake demo\")\n"
                    "+    return 0\n"
                    "+\n"
                    "+\n"
                    "+if __name__ == \"__main__\":\n"
                    "+    raise SystemExit(main())\n"
                )
                return ProposedPatch(
                    skill_name="ollama",
                    patch=patch_text,
                    changed_files=["snake.py"],
                    summary="Ollama proposed snake.py.",
                )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = create_app(project_path=root)
            app.state.session_store.patch_generator = FakePatchGenerator()
            client = TestClient(app)
            before_exists = (root / "snake.py").exists()
            plan = client.post("/api/tasks/plan", json={"task": SNAKE_TASK, "mode": "review"})
            self.assertEqual(plan.status_code, 200)
            task_id = plan.json()["task_id"]
            proposed = client.post(f"/api/tasks/{task_id}/propose").json()
            self.assertFalse(before_exists)
            self.assertEqual(proposed["status"], "waiting_approval")
            self.assertIn("snake.py", proposed["proposed_files"])
            self.assertIn("+++ b/snake.py", proposed["proposed_diff"])
            self.assertFalse((root / "snake.py").exists())
            unapproved = client.post(f"/api/tasks/{task_id}/run").json()
            self.assertEqual(unapproved["status"], "waiting_approval")
            self.assertFalse((root / "snake.py").exists())
            approval = proposed["pending_approvals"][0]
            approve = client.post(
                f"/api/tasks/{task_id}/approve",
                json={"step_id": approval["step_id"], "action": approval["action"]},
            )
            self.assertEqual(approve.status_code, 200)
            self.assertEqual(approve.json()["status"], "approved")
            run = client.post(f"/api/tasks/{task_id}/run").json()
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["skill_name"], "ollama")
            self.assertTrue((root / "snake.py").exists())
            self.assertIn("python -m py_compile snake.py", run["final_report"])
            self.assertIn("provider: ollama", run["final_report"])

    def test_unknown_task_with_ollama_unavailable_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://127.0.0.1:1"}):
                client = TestClient(create_app(project_path=root))
            task_id = client.post(
                "/api/tasks/plan",
                json={"task": "Сделай неизвестную новую функцию", "mode": "review"},
            ).json()["task_id"]
            proposed = client.post(f"/api/tasks/{task_id}/propose")
            self.assertEqual(proposed.status_code, 200)
            self.assertEqual(proposed.json()["status"], "failed")
            self.assertEqual(list(root.iterdir()), [])

    def test_approval_endpoint_requires_known_task_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            response = client.post(
                "/api/tasks/missing/approve",
                json={"step_id": "step_missing", "action": "apply_patch"},
            )
            self.assertEqual(response.status_code, 404)

    def test_run_respects_review_mode_pending_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.txt").write_text("before\n", encoding="utf-8")
            app = create_app(project_path=root)
            client = TestClient(app)
            response = client.post("/api/tasks/plan", json={"task": "Patch sample", "mode": "review"})
            self.assertEqual(response.status_code, 200)
            task_id = response.json()["task_id"]
            store = app.state.session_store
            task_session = store.get_task(task_id)
            self.assertIsNotNone(task_session)
            assert task_session is not None
            task_session.plan.steps = [
                PlanStep.create(
                    type="patch",
                    description="Patch sample file.",
                    required_tool="apply_patch",
                    input={
                        "patch": (
                            "--- a/sample.txt\n"
                            "+++ b/sample.txt\n"
                            "@@ -1 +1 @@\n"
                            "-before\n"
                            "+after\n"
                        )
                    },
                )
            ]
            run_response = client.post(f"/api/tasks/{task_id}/run")
            self.assertEqual(run_response.status_code, 200)
            data = run_response.json()
            self.assertEqual(data["status"], "waiting_approval")
            self.assertTrue(data["pending_approvals"])
            self.assertEqual((root / "sample.txt").read_text(encoding="utf-8"), "before\n")


if __name__ == "__main__":
    unittest.main()
