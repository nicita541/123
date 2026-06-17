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
            self.assertIn("Локальный coding-агент", index.text)
            self.assertIn("Рабочая область", index.text)
            self.assertIn("Ожидают подтверждения", index.text)
            self.assertIn("Терминал", index.text)

    def test_index_contains_russian_interface_labels(self) -> None:
        text = Path("src/complex_agent/web/index.html").read_text(encoding="utf-8")
        labels = [
            "Рабочая область",
            "Файлы",
            "Изменения",
            "Чат",
            "План",
            "Подтверждение",
            "Терминал",
            "Проверки",
            "Журнал",
            "Отчёт",
        ]
        for label in labels:
            with self.subTest(label=label):
                self.assertIn(label, text)
        self.assertNotIn("Codex", text)

    def test_styles_contain_workspace_layout_classes(self) -> None:
        styles = Path("src/complex_agent/web/styles.css").read_text(encoding="utf-8")
        for class_name in [
            ".workspace-header",
            ".workspace-grid",
            ".sidebar-panel",
            ".chat-workspace",
            ".action-panel",
            ".workbench",
            ".diff-line.added",
            ".diff-line.deleted",
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
        self.assertIn("/api/files", script)
        self.assertIn("/api/files/preview", script)
        self.assertIn("/api/git/diff", script)
