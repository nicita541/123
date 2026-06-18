from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from complex_agent.api.server import create_app
from complex_agent.codegen.patch_generator import PatchGenerator
from complex_agent.codegen.patch_generator import ProposedPatch
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep


CALCULATOR_TASK = "Создай консольный калькулятор на Python"


class ProductizationApiTests(unittest.TestCase):
    def _client(self, project: str, data: str) -> tuple[TestClient, Any]:
        app = create_app(project_path=project, app_data_path=data)
        app.state.session_store.patch_generator = PatchGenerator(
            app.state.session_store.runtime.safety,
            allow_demo_fallback=True,
        )
        return TestClient(app), app

    def _complete_calculator(self, client: TestClient) -> str:
        task_id = client.post(
            "/api/tasks/plan", json={"task": CALCULATOR_TASK, "mode": "review"}
        ).json()["task_id"]
        proposed = client.post(f"/api/tasks/{task_id}/propose").json()
        approval = proposed["pending_approvals"][0]
        client.post(
            f"/api/tasks/{task_id}/approve",
            json={"step_id": approval["step_id"], "action": approval["action"]},
        )
        completed = client.post(f"/api/tasks/{task_id}/run")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        return str(task_id)

    def test_history_diff_and_report_survive_application_restart(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
            first, _ = self._client(project, data)
            task_id = self._complete_calculator(first)

            second, _ = self._client(project, data)
            tasks = second.get("/api/tasks").json()["tasks"]
            self.assertIn(task_id, [task["id"] for task in tasks])
            restored = second.get(f"/api/tasks/{task_id}").json()
            self.assertIn("calculator.py", restored["proposed_diff"])
            self.assertIn("OK: all calculator self-tests passed", restored["verification_output"])
            self.assertIn("Как запустить", restored["final_report"])

    def test_rollback_deletes_created_file_only_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
            client, _ = self._client(project, data)
            task_id = self._complete_calculator(client)
            target = Path(project, "calculator.py")
            self.assertTrue(target.exists())
            denied = client.post(
                f"/api/tasks/{task_id}/rollback",
                json={"confirm_created_deletions": False},
            )
            self.assertEqual(denied.status_code, 409)
            self.assertTrue(target.exists())
            restored = client.post(
                f"/api/tasks/{task_id}/rollback",
                json={"confirm_created_deletions": True},
            )
            self.assertEqual(restored.status_code, 200)
            self.assertFalse(target.exists())

    def test_rollback_detects_external_change(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
            client, _ = self._client(project, data)
            task_id = self._complete_calculator(client)
            Path(project, "calculator.py").write_text("external change\n", encoding="utf-8")
            response = client.post(
                f"/api/tasks/{task_id}/rollback",
                json={"confirm_created_deletions": True},
            )
            self.assertEqual(response.status_code, 409)
            self.assertIn("conflict", response.text.lower())

    def test_multiple_projects_have_isolated_histories(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root_a,
            tempfile.TemporaryDirectory() as root_b,
            tempfile.TemporaryDirectory() as data,
        ):
            client, _ = self._client(root_a, data)
            first_project = client.get("/api/project").json()["id"]
            second_project = client.post("/api/projects", json={"root_path": root_b}).json()["id"]
            task_id = client.post(
                "/api/tasks/plan",
                json={"task": CALCULATOR_TASK, "mode": "review", "project_id": second_project},
            ).json()["task_id"]
            self.assertEqual(
                client.get(f"/api/tasks?project_id={first_project}").json()["tasks"], []
            )
            second_tasks = client.get(f"/api/tasks?project_id={second_project}").json()["tasks"]
            self.assertEqual([task["id"] for task in second_tasks], [task_id])

    def test_container_mode_registers_only_exact_mounted_project_paths(self) -> None:
        mount_id = "project_12345678"
        with (
            tempfile.TemporaryDirectory() as projects,
            tempfile.TemporaryDirectory() as data,
        ):
            default_project = Path(projects, "default")
            mounted_project = Path(projects, mount_id)
            unsafe_project = Path(projects, "project_abcdefgh")
            default_project.mkdir()
            mounted_project.mkdir()
            unsafe_project.mkdir()
            with patch.dict(os.environ, {"AGENT_PROJECTS_ROOT": projects}):
                client, _ = self._client(str(default_project), data)
                response = client.post(
                    "/api/projects/register",
                    json={
                        "name": "Todo",
                        "mount_id": mount_id,
                        "host_path": r"F:\1",
                        "container_path": str(mounted_project),
                    },
                )
                self.assertEqual(response.status_code, 200)
                project = response.json()
                self.assertEqual(project["mount_id"], mount_id)
                self.assertEqual(project["host_path"], r"F:\1")
                self.assertEqual(project["container_path"], str(mounted_project.resolve()))

                bypass = client.post("/api/projects", json={"root_path": str(mounted_project)})
                self.assertEqual(bypass.status_code, 400)

                wrong_mapping = client.post(
                    "/api/projects/register",
                    json={
                        "name": "Wrong",
                        "mount_id": "project_abcdefgh",
                        "host_path": r"F:\2",
                        "container_path": str(mounted_project),
                    },
                )
                self.assertEqual(wrong_mapping.status_code, 400)

                drive_root = client.post(
                    "/api/projects/register",
                    json={
                        "name": "Unsafe",
                        "mount_id": "project_abcdefgh",
                        "host_path": "F:\\",
                        "container_path": str(unsafe_project),
                    },
                )
                self.assertEqual(drive_root.status_code, 400)

    def test_application_data_cannot_be_selected_as_project(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
            client, _ = self._client(project, data)
            response = client.post("/api/projects", json={"root_path": data})
            self.assertEqual(response.status_code, 400)
            self.assertIn("Application data", response.text)

    def test_settings_repeat_and_continue_persist(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
            client, _ = self._client(project, data)
            task_id = client.post(
                "/api/tasks/plan", json={"task": CALCULATOR_TASK, "mode": "review"}
            ).json()["task_id"]
            settings = client.post(
                "/api/settings",
                json={"selected_model": "local-test", "max_fix_iterations": 2},
            )
            self.assertEqual(settings.status_code, 200)
            self.assertEqual(settings.json()["max_fix_iterations"], 2)
            repeated = client.post(f"/api/tasks/{task_id}/repeat")
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(repeated.json()["parent_task_id"], task_id)
            continued = client.post(
                f"/api/tasks/{task_id}/continue", json={"message": "Добавь ещё одну операцию"}
            )
            self.assertEqual(continued.status_code, 200)
            messages = client.get(f"/api/tasks/{task_id}/messages").json()["messages"]
            self.assertEqual(messages[-1]["content"], "Добавь ещё одну операцию")

    def test_failed_verification_can_propose_approved_fix(self) -> None:
        class SequentialGenerator:
            def __init__(self) -> None:
                self.calls = 0

            def create_plan(self, task):  # type: ignore[no-untyped-def]
                return Plan.create(
                    task_id=task.id,
                    goal=task.normalized_goal,
                    steps=[
                        PlanStep.create(
                            type="patch",
                            description="Create broken.py",
                            required_tool="apply_patch",
                            approval_required=True,
                        )
                    ],
                )

            def propose(self, task, project_root, **kwargs):  # type: ignore[no-untyped-def]
                self.calls += 1
                if self.calls == 1:
                    patch = "--- /dev/null\n+++ b/broken.py\n@@ -0,0 +1 @@\n+def broken(:\n"
                else:
                    patch = (
                        "--- a/broken.py\n+++ b/broken.py\n@@ -1 +1,2 @@\n"
                        "-def broken(:\n+def fixed():\n+    return True\n"
                    )
                return ProposedPatch(
                    skill_name="ollama",
                    patch=patch,
                    changed_files=["broken.py"],
                    summary="Sequential proposal",
                )

        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
            app = create_app(project_path=project, app_data_path=data)
            app.state.session_store.patch_generator = SequentialGenerator()
            client = TestClient(app)
            task_id = client.post(
                "/api/tasks/plan", json={"task": "Create broken.py", "mode": "review"}
            ).json()["task_id"]
            first = client.post(f"/api/tasks/{task_id}/propose").json()
            approval = first["pending_approvals"][0]
            client.post(
                f"/api/tasks/{task_id}/approve",
                json={"step_id": approval["step_id"], "action": approval["action"]},
            )
            failed = client.post(f"/api/tasks/{task_id}/run").json()
            self.assertEqual(failed["status"], "needs_fix")

            fixed = client.post(f"/api/tasks/{task_id}/propose-fix").json()
            approval = fixed["pending_approvals"][0]
            client.post(
                f"/api/tasks/{task_id}/approve",
                json={"step_id": approval["step_id"], "action": approval["action"]},
            )
            completed = client.post(f"/api/tasks/{task_id}/run").json()
            self.assertEqual(completed["status"], "completed")
            self.assertTrue(Path(project, "broken.py").is_file())


if __name__ == "__main__":
    unittest.main()
