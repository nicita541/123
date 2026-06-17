from __future__ import annotations


class DiffReviewer:
    def review(self, diff: str) -> str:
        if not diff.strip():
            return "No diff was detected."
        files = [line[4:] for line in diff.splitlines() if line.startswith("+++ ")]
        return f"Diff touches {len(files)} files: {', '.join(files) if files else 'unknown'}."

