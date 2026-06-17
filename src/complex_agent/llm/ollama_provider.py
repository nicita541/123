from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from complex_agent.llm.provider import Provider


DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT_SECONDS = 60


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    provider: str = "ollama"
    fallback_provider: str = "deterministic"


class OllamaProvider(Provider):
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._urlopen = urlopen or urllib.request.build_opener(urllib.request.ProxyHandler({})).open

    @classmethod
    def from_settings(cls, settings: OllamaSettings, *, urlopen: Callable[..., Any] | None = None) -> "OllamaProvider":
        return cls(
            base_url=settings.base_url,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
            urlopen=urlopen,
        )

    def complete(self, prompt: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        data = self._post_json("/api/generate", payload)
        response = data.get("response")
        if not isinstance(response, str):
            raise OllamaError("Ollama response did not contain a text response.")
        return response

    def complete_structured(self, prompt: str, schema_hint: dict[str, Any] | None = None) -> dict[str, Any] | str:
        full_prompt = prompt
        if schema_hint:
            full_prompt += "\n\nReturn valid JSON matching this shape:\n"
            full_prompt += json.dumps(schema_hint, ensure_ascii=False, indent=2)
        text = self.complete(full_prompt).strip()
        try:
            return json.loads(_extract_json(text))
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc

    def is_reachable(self) -> bool:
        try:
            self.list_models()
        except OllamaError:
            return False
        return True

    def list_models(self) -> list[str]:
        data = self._get_json("/api/tags")
        models = data.get("models", [])
        if not isinstance(models, list):
            return []
        names: list[str] = []
        for item in models:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
        return names

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        return self._send(request)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(request)

    def _send(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            raise OllamaError(f"Ollama is unavailable at {self.base_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise OllamaError(f"Ollama request timed out after {self.timeout_seconds}s.") from exc
        except OSError as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc
        if "error" in parsed:
            raise OllamaError(f"Ollama error: {parsed['error']}")
        return parsed


def load_ollama_settings(config_path: str | Path | None = None) -> OllamaSettings:
    config = _read_models_config(config_path)
    llm = config.get("llm", {}) if isinstance(config, dict) else {}
    ollama = llm.get("ollama", {}) if isinstance(llm, dict) else {}
    base_url = os.environ.get("OLLAMA_BASE_URL") or str(ollama.get("base_url", DEFAULT_BASE_URL))
    model = os.environ.get("OLLAMA_MODEL") or str(ollama.get("model", DEFAULT_MODEL))
    timeout = int(ollama.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    return OllamaSettings(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
        provider=str(llm.get("provider", "ollama")) if isinstance(llm, dict) else "ollama",
        fallback_provider=str(llm.get("fallback_provider", "deterministic")) if isinstance(llm, dict) else "deterministic",
    )


def _read_models_config(config_path: str | Path | None) -> dict[str, Any]:
    path = Path(config_path) if config_path else Path(__file__).resolve().parents[3] / "config" / "models.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _extract_json(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
