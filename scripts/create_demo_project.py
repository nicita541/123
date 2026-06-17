from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path("demo_project")
    root.mkdir(exist_ok=True)
    (root / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    print(root)


if __name__ == "__main__":
    main()

