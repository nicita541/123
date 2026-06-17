from __future__ import annotations

import socket
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import uvicorn

from complex_agent.api.server import create_app


DEFAULT_HOST = "127.0.0.1"
WINDOW_TITLE = "Локальный агент"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 720


def find_free_port(host: str = DEFAULT_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def desktop_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def run_desktop_app(
    *,
    project_path: str | Path,
    host: str = DEFAULT_HOST,
    port: int | None = None,
) -> None:
    webview = _load_webview()
    selected_port = port or find_free_port(host)
    app = create_app(project_path=project_path, host=host)
    config = uvicorn.Config(app, host=host, port=selected_port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="complex-agent-desktop-server")
    thread.start()
    url = desktop_url(host, selected_port)
    try:
        _wait_until_ready(url)
        window = webview.create_window(
            WINDOW_TITLE,
            url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
        )
        webview.start()
        _ = window
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _load_webview() -> Any:
    try:
        import webview  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            'Desktop mode requires pywebview. Install with: pip install -e ".[desktop]"'
        ) from exc
    return webview


def _wait_until_ready(url: str, *, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with opener.open(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - retry until timeout
            last_error = exc
            time.sleep(0.15)
    raise RuntimeError(f"Desktop backend did not become ready at {url}: {last_error}")
