from __future__ import annotations

import unittest
from pathlib import Path


class DockerFilesTests(unittest.TestCase):
    def test_required_docker_files_exist(self) -> None:
        for path in [
            "Dockerfile",
            "docker-compose.yml",
            ".dockerignore",
            "scripts/docker_build.ps1",
            "scripts/docker_run.ps1",
            "docs/docker.md",
        ]:
            with self.subTest(path=path):
                self.assertTrue(Path(path).is_file())

    def test_dockerfile_uses_python_312_non_root_and_workspace(self) -> None:
        text = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.12-slim", text)
        self.assertIn("USER agent", text)
        self.assertIn("AGENT_PROJECT_ROOT=/workspace", text)
        self.assertIn('"--project", "/workspace"', text)
        self.assertNotIn("COPY . .", text)

    def test_compose_mounts_only_selected_workspace(self) -> None:
        text = Path("docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("agent-app:", text)
        self.assertIn('"8765:8765"', text)
        self.assertIn("AGENT_PROJECT_ROOT: /workspace", text)
        self.assertIn("${AGENT_WORKSPACE:-./examples/demo_project}:/workspace", text)
        self.assertIn("http://host.docker.internal:11434", text)
        self.assertNotIn("/:/workspace", text)

    def test_dockerignore_excludes_generated_and_sensitive_paths(self) -> None:
        text = Path(".dockerignore").read_text(encoding="utf-8")
        for value in [".git", ".agent", ".venv", "__pycache__", ".env"]:
            with self.subTest(value=value):
                self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
