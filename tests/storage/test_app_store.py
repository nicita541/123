from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from complex_agent.storage.app_store import AppStore


class AppStoreTests(unittest.TestCase):
    def test_legacy_project_rows_gain_container_mapping_columns(self) -> None:
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as project_root:
            database = Path(data, "app.sqlite3")
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    """CREATE TABLE projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        root_path TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_opened_at TEXT NOT NULL,
                        is_archived INTEGER NOT NULL DEFAULT 0,
                        default_model TEXT,
                        default_mode TEXT NOT NULL DEFAULT 'review',
                        created_by TEXT NOT NULL DEFAULT 'local-user',
                        visibility TEXT NOT NULL DEFAULT 'private'
                    )"""
                )
                connection.execute(
                    """INSERT INTO projects(
                        id, name, root_path, created_at, updated_at, last_opened_at
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    ("legacy", "Legacy", str(Path(project_root).resolve()), "now", "now", "now"),
                )
                connection.commit()

            migrated = AppStore(data).get_project("legacy")
            self.assertIsNotNone(migrated)
            assert migrated is not None
            self.assertEqual(migrated["container_path"], str(Path(project_root).resolve()))
            self.assertIsNone(migrated["mount_id"])
            self.assertIsNone(migrated["host_path"])

    def test_projects_tasks_messages_and_settings_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as project_root:
            first = AppStore(data)
            project = first.upsert_project(project_root, name="Project A")
            first.create_task(
                task_id="task_1",
                project_id=str(project["id"]),
                title="Persist me",
                user_message="Persist me",
                status="planned",
                mode="review",
                provider="ollama",
                model="model",
            )
            first.add_message("task_1", "user", "Persist me")
            first.set_settings({"max_fix_iterations": 2})

            second = AppStore(data)
            restored_project = second.get_project(str(project["id"]))
            restored_task = second.get_task("task_1")
            self.assertIsNotNone(restored_project)
            self.assertIsNotNone(restored_task)
            assert restored_project is not None and restored_task is not None
            self.assertEqual(restored_project["name"], "Project A")
            self.assertEqual(restored_task["title"], "Persist me")
            self.assertEqual(second.list_messages("task_1")[0]["content"], "Persist me")
            self.assertEqual(second.get_settings()["max_fix_iterations"], 2)

    def test_tasks_are_filtered_by_project(self) -> None:
        with (
            tempfile.TemporaryDirectory() as data,
            tempfile.TemporaryDirectory() as root_a,
            tempfile.TemporaryDirectory() as root_b,
        ):
            store = AppStore(data)
            project_a = store.upsert_project(root_a)
            project_b = store.upsert_project(root_b)
            for task_id, project_id in (("a", project_a["id"]), ("b", project_b["id"])):
                store.create_task(
                    task_id=task_id,
                    project_id=str(project_id),
                    title=task_id,
                    user_message=task_id,
                    status="planned",
                    mode="review",
                    provider="ollama",
                    model="model",
                )
            self.assertEqual([row["id"] for row in store.list_tasks(str(project_a["id"]))], ["a"])
            self.assertEqual([row["id"] for row in store.list_tasks(str(project_b["id"]))], ["b"])


if __name__ == "__main__":
    unittest.main()
