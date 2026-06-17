from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        conn = self.connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    summary TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    run_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable[object] = ()) -> None:
        conn = self.connect()
        try:
            conn.execute(sql, tuple(params))
            conn.commit()
        finally:
            conn.close()

    def query(self, sql: str, params: Iterable[object] = ()) -> list[tuple[object, ...]]:
        conn = self.connect()
        try:
            return list(conn.execute(sql, tuple(params)))
        finally:
            conn.close()
