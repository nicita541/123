from __future__ import annotations


class RiskAnalyzer:
    def analyze(self, *, changed_files: list[str], errors: list[str]) -> str:
        if errors:
            return "high"
        if len(changed_files) > 5:
            return "medium"
        return "low"

