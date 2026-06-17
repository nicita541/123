from __future__ import annotations

import re


class SecretsGuard:
    def __init__(self, patterns: list[str] | None = None) -> None:
        self.patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                patterns
                or [
                    r"api[_-]?key\s*[:=]\s*['\"]?[^'\"\s]+",
                    r"secret\s*[:=]\s*['\"]?[^'\"\s]+",
                    r"token\s*[:=]\s*['\"]?[^'\"\s]+",
                    r"password\s*[:=]\s*['\"]?[^'\"\s]+",
                ]
            )
        ]

    def redact(self, text: str) -> str:
        redacted = text
        for pattern in self.patterns:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

