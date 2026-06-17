from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from complex_agent.llm.ollama_provider import OllamaError, OllamaProvider, load_ollama_settings


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OllamaProviderTests(unittest.TestCase):
    def test_complete_forms_generate_request(self) -> None:
        calls = []

        def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
            calls.append((request, timeout))
            return _FakeResponse({"response": "ok"})

        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="qwen2.5-coder:7b",
            timeout_seconds=12,
            urlopen=fake_urlopen,
        )
        self.assertEqual(provider.complete("hello"), "ok")
        request, timeout = calls[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(timeout, 12)
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "qwen2.5-coder:7b")
        self.assertEqual(body["prompt"], "hello")
        self.assertFalse(body["stream"])

    def test_unavailable_ollama_returns_clear_error(self) -> None:
        def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
            raise urllib.error.URLError("connection refused")

        provider = OllamaProvider(urlopen=fake_urlopen)
        with self.assertRaises(OllamaError) as ctx:
            provider.complete("hello")
        self.assertIn("Ollama is unavailable", str(ctx.exception))

    def test_list_models_uses_tags_endpoint(self) -> None:
        calls = []

        def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
            calls.append((request, timeout))
            return _FakeResponse({"models": [{"name": "qwen2.5-coder:7b"}, {"name": "llama3.1:8b"}]})

        provider = OllamaProvider(urlopen=fake_urlopen, timeout_seconds=5)
        self.assertEqual(provider.list_models(), ["qwen2.5-coder:7b", "llama3.1:8b"])
        request, timeout = calls[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/tags")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 5)

    def test_env_override_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "models.yaml"
            config.write_text(
                "llm:\n"
                "  provider: ollama\n"
                "  ollama:\n"
                "    base_url: http://from-config:11434\n"
                "    model: config-model\n"
                "    timeout_seconds: 7\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"OLLAMA_BASE_URL": "http://env:11434", "OLLAMA_MODEL": "env-model"},
            ):
                settings = load_ollama_settings(config)
            self.assertEqual(settings.base_url, "http://env:11434")
            self.assertEqual(settings.model, "env-model")
            self.assertEqual(settings.timeout_seconds, 7)


if __name__ == "__main__":
    unittest.main()
