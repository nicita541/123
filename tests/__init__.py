"""Test package."""
from __future__ import annotations

import os
import tempfile


# Unit tests must not depend on a running local model or write into the user's app data.
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:1"
os.environ["COMPLEX_AGENT_DATA_DIR"] = tempfile.mkdtemp(prefix="complex-agent-tests-")
