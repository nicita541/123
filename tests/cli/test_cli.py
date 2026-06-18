from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from complex_agent.ui.cli import main
from complex_agent.ui.cli import build_parser, create_serve_app


class CliTests(unittest.TestCase):
    def test_tools_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            code = main(["--project", temp, "tools"])
            self.assertEqual(code, 0)

    def test_disabled_tools_are_not_shown_as_fully_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = StringIO()
            with redirect_stdout(output):
                code = main(["--project", temp, "tools"])
            self.assertEqual(code, 0)
            lines = output.getvalue().splitlines()
            self.assertFalse(any("git_commit" in line for line in lines))
            self.assertIn(
                "internal\tfinal_report\tReturn a simple report placeholder for tool-only final steps.",
                lines,
            )
            self.assertNotIn("final_report", lines)

    def test_plan_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as app_data:
            Path(temp, "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://127.0.0.1:1"}):
                code = main(["--project", temp, "--app-data", app_data, "plan", "Audit"])
            self.assertEqual(code, 1)

    def test_read_only_commands_do_not_create_agent_state(self) -> None:
        read_only_commands = [
            ["status"],
            ["tools"],
            ["config"],
            ["plan", "Audit"],
        ]
        for command in read_only_commands:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as temp:
                    with tempfile.TemporaryDirectory() as app_data:
                        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://127.0.0.1:1"}):
                            code = main(["--project", temp, "--app-data", app_data, *command])
                    self.assertEqual(code, 1 if command[0] == "plan" else 0)
                    self.assertFalse(Path(temp, ".agent").exists())

    def test_audit_persists_failed_ollama_task_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as app_data:
            Path(temp, "sample.py").write_text("# TODO: demo\n", encoding="utf-8")
            with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://127.0.0.1:1"}):
                code = main(
                    ["--project", temp, "--app-data", app_data, "audit", "Audit this project"]
                )
            self.assertEqual(code, 1)
            self.assertTrue(Path(app_data, "app.sqlite3").exists())
            self.assertFalse(Path(temp, ".agent").exists())

    def test_serve_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--project", ".", "--host", "127.0.0.1", "--port", "8765"])
        self.assertEqual(args.command, "serve")
        self.assertEqual(args.serve_project, ".")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8765)

    def test_serve_app_can_be_created_without_running_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = create_serve_app(temp, "127.0.0.1")
            self.assertEqual(app.title, "Complex AI Coding Agent Local App")


if __name__ == "__main__":
    unittest.main()
