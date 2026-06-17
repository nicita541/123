from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from complex_agent.api.server import create_app
from complex_agent.planning.plan_step import PlanStep


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
            self.assertFalse(Path(temp, ".agent").exists())

    def test_tools_returns_tool_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            response = client.get("/api/tools")
            self.assertEqual(response.status_code, 200)
            statuses = {tool["name"]: tool["status"] for tool in response.json()["tools"]}
            self.assertEqual(statuses["git_commit"], "disabled")
            self.assertEqual(statuses["final_report"], "internal")
            self.assertEqual(statuses["read_file"], "enabled")

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
            self.assertEqual(data["status"], "pending_approval")
            self.assertTrue(data["pending_approvals"])
            self.assertEqual((root / "sample.txt").read_text(encoding="utf-8"), "before\n")
