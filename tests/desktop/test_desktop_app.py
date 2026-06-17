from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from complex_agent.desktop.app import DEFAULT_HOST, desktop_url, find_free_port, run_desktop_app
from complex_agent.ui.cli import build_parser


class DesktopAppTests(unittest.TestCase):
    def test_desktop_url_is_localhost(self) -> None:
        self.assertEqual(desktop_url(DEFAULT_HOST, 8765), "http://127.0.0.1:8765")

    def test_find_free_port_returns_int(self) -> None:
        port = find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)

    def test_desktop_command_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["desktop", "--project", "F:\\1"])
        self.assertEqual(args.command, "desktop")
        self.assertEqual(args.desktop_project, "F:\\1")

    def test_missing_pywebview_shows_friendly_error(self) -> None:
        with patch.dict(sys.modules, {"webview": None}):
            with self.assertRaises(RuntimeError) as ctx:
                run_desktop_app(project_path=".", port=8765)
        self.assertIn('pip install -e ".[desktop]"', str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
