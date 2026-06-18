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

    def test_dockerfile_uses_python_312_non_root_and_projects_root(self) -> None:
        text = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.12-slim", text)
        self.assertIn("USER agent", text)
        self.assertIn("AGENT_PROJECTS_ROOT=/projects", text)
        self.assertIn('"--project", "/projects/docker_workspace"', text)
        self.assertIn("HEALTHCHECK", text)
        self.assertNotIn("COPY . .", text)

    def test_compose_runs_backend_and_containerized_ollama(self) -> None:
        text = Path("docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("backend:", text)
        self.assertIn("ollama:", text)
        self.assertIn("model-init:", text)
        self.assertIn("data-init:", text)
        self.assertIn('"127.0.0.1:8765:8765"', text)
        self.assertIn("AGENT_PROJECTS_ROOT: /projects", text)
        self.assertIn("${AGENT_PROJECTS_ROOT:-./examples}:/projects", text)
        self.assertIn("COMPLEX_AGENT_DATA_DIR: /data", text)
        self.assertIn("agent-data:/data", text)
        self.assertIn("http://ollama:11434", text)
        self.assertIn("condition: service_completed_successfully", text)
        self.assertNotIn("host.docker.internal", text)
        self.assertNotIn("/:/projects", text)

    def test_dockerignore_excludes_generated_and_sensitive_paths(self) -> None:
        text = Path(".dockerignore").read_text(encoding="utf-8")
        for value in [".git", ".agent", ".venv", "__pycache__", ".env", "desktop", "bin", "obj"]:
            with self.subTest(value=value):
                self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
