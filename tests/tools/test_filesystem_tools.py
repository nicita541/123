from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from complex_agent.safety.approval_gate import ApprovalGate
from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.filesystem.patch_tool import ApplyPatchTool
from complex_agent.tools.filesystem.read_file_tool import ReadFileTool
from complex_agent.tools.filesystem.search_files_tool import SearchFilesTool


class FilesystemToolTests(unittest.TestCase):
    def test_read_file_redacts_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config.txt").write_text("api_key=abc123\n", encoding="utf-8")
            context = ToolContext(root, SafetyPolicy(root))
            result = ReadFileTool().run({"path": "config.txt"}, context)
            self.assertTrue(result.success)
            self.assertIn("[REDACTED]", result.content)

    def test_apply_patch_modifies_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "hello.txt").write_text("hello\nworld\n", encoding="utf-8")
            policy = SafetyPolicy(root, approval_gate=ApprovalGate(auto_approve=True))
            context = ToolContext(root, policy)
            patch = """--- a/hello.txt
+++ b/hello.txt
@@ -1,2 +1,2 @@
 hello
-world
+agent
"""
            result = ApplyPatchTool().run({"patch": patch}, context)
            self.assertTrue(result.success, result.error)
            self.assertEqual((root / "hello.txt").read_text(encoding="utf-8"), "hello\nagent\n")

    def test_search_files_does_not_return_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env").write_text("NEEDLE=value\n", encoding="utf-8")
            (root / "safe.txt").write_text("NEEDLE=safe\n", encoding="utf-8")
            context = ToolContext(root, SafetyPolicy(root))
            result = SearchFilesTool().run({"query": "NEEDLE", "glob": "*"}, context)
            self.assertTrue(result.success)
            self.assertNotIn(".env", result.content)
            self.assertIn("safe.txt", result.content)

    def test_search_files_does_not_return_secret_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "safe.txt").write_text("SECRET_TOKEN=abc123\n", encoding="utf-8")
            context = ToolContext(root, SafetyPolicy(root))
            result = SearchFilesTool().run({"query": "SECRET_TOKEN", "glob": "*"}, context)
            self.assertTrue(result.success)
            self.assertNotIn("SECRET_TOKEN", result.content)
            self.assertNotIn("abc123", result.content)

    def test_search_files_does_not_return_forbidden_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            secret_dir = root / "secret"
            secret_dir.mkdir()
            (secret_dir / "config.txt").write_text("NEEDLE=hidden\n", encoding="utf-8")
            context = ToolContext(root, SafetyPolicy(root))
            result = SearchFilesTool().run({"query": "NEEDLE", "glob": "*"}, context)
            self.assertTrue(result.success)
            self.assertNotIn("secret", result.content)
            self.assertNotIn("hidden", result.content)

    def test_read_file_and_search_files_use_same_file_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env").write_text("NEEDLE=hidden\n", encoding="utf-8")
            context = ToolContext(root, SafetyPolicy(root))
            read_result = ReadFileTool().run({"path": ".env"}, context)
            search_result = SearchFilesTool().run({"query": "NEEDLE", "glob": "*"}, context)
            self.assertFalse(read_result.success)
            self.assertTrue(search_result.success)
            self.assertEqual(search_result.content, "")


if __name__ == "__main__":
    unittest.main()
