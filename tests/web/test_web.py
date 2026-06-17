from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from complex_agent.api.server import create_app


class WebTests(unittest.TestCase):
    def test_static_files_exist(self) -> None:
        web_root = Path("src/complex_agent/web")
        self.assertTrue((web_root / "index.html").exists())
        self.assertTrue((web_root / "app.js").exists())
        self.assertTrue((web_root / "styles.css").exists())

    def test_server_serves_frontend_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app(project_path=temp))
            index = client.get("/")
            script = client.get("/static/app.js")
            styles = client.get("/static/styles.css")
            self.assertEqual(index.status_code, 200)
            self.assertEqual(script.status_code, 200)
            self.assertEqual(styles.status_code, 200)
            self.assertIn("Локальный агент", index.text)
            self.assertIn("Что изменить в проекте?", index.text)
            self.assertIn("Среда", index.text)
            self.assertIn("Запросите внесение изменений", index.text)

    def test_index_contains_final_russian_interface_labels(self) -> None:
        text = Path("src/complex_agent/web/index.html").read_text(encoding="utf-8")
        labels = [
            "Локальный агент",
            "Новый чат",
            "Проекты",
            "История",
            "Что изменить в проекте?",
            "Среда",
            "Изменения",
            "Модель",
            "Provider",
            "Статус модели",
            "Запросите внесение изменений",
        ]
        for label in labels:
            with self.subTest(label=label):
                self.assertIn(label, text)
        self.assertNotIn("Codex", text)
        self.assertNotIn("OpenAI", text)

    def test_styles_contain_final_workspace_layout_classes(self) -> None:
        styles = Path("src/complex_agent/web/styles.css").read_text(encoding="utf-8")
        for class_name in [
            ".sidebar",
            ".main",
            ".task-feed",
            ".environment-card",
            ".composer",
            ".feed-card",
            ".diff-code",
        ]:
            with self.subTest(class_name=class_name):
                self.assertIn(class_name, styles)

    def test_frontend_has_no_direct_dangerous_endpoints(self) -> None:
        script = Path("src/complex_agent/web/app.js").read_text(encoding="utf-8")
        forbidden_fragments = [
            "/api/shell",
            "/api/command",
            "/api/write",
            "/api/apply-patch",
            "/api/git/command",
        ]
        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, script)
        self.assertIn("/api/status", script)
        self.assertIn("/api/workspace", script)
        self.assertIn("/api/tasks/plan", script)
        self.assertIn("/api/tasks/${state.taskId}/propose", script)
