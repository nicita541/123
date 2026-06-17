from __future__ import annotations


class CodeReviewer:
    def review(self, text: str) -> list[str]:
        warnings: list[str] = []
        if "TODO" in text or "FIXME" in text:
            warnings.append("Remaining TODO/FIXME markers detected.")
        return warnings

