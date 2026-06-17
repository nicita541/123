from __future__ import annotations


class ResponseParser:
    def parse_text(self, response: str) -> str:
        return response.strip()

