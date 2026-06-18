from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from complex_agent.storage.app_paths import AppPaths
from complex_agent.utils.ids import new_id


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AppStore:
    def __init__(self, paths: AppPaths | str | Path | None = None) -> None:
        self.paths = paths if isinstance(paths, AppPaths) else AppPaths.resolve(paths)
        self.paths.ensure()
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.paths.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self) -> None:
        connection = self.connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS local_users (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL CHECK(role IN ('owner', 'developer', 'viewer')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    mount_id TEXT,
                    host_path TEXT,
                    container_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_opened_at TEXT NOT NULL,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    default_model TEXT,
                    default_mode TEXT NOT NULL DEFAULT 'review',
                    created_by TEXT NOT NULL DEFAULT 'local-user',
                    visibility TEXT NOT NULL DEFAULT 'private'
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id),
                    parent_task_id TEXT REFERENCES tasks(id),
                    title TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'ollama',
                    model TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    local_user_id TEXT NOT NULL DEFAULT 'local-user',
                    created_by TEXT NOT NULL DEFAULT 'local-user',
                    assigned_to TEXT NOT NULL DEFAULT 'local-user',
                    visibility TEXT NOT NULL DEFAULT 'private',
                    fix_iteration INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_project_updated
                    ON tasks(project_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS task_messages (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_plans (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_proposals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    proposed_diff TEXT NOT NULL,
                    changed_files_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    action TEXT NOT NULL DEFAULT 'apply_patch',
                    skill_name TEXT,
                    fix_iteration INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    applied_at TEXT,
                    rolled_back_at TEXT,
                    snapshot_id TEXT
                );
                CREATE TABLE IF NOT EXISTS task_approvals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    step_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    verification_command TEXT NOT NULL DEFAULT '',
                    verification_argv_json TEXT NOT NULL DEFAULT '[]',
                    verification_output TEXT NOT NULL DEFAULT '',
                    report TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_snapshots (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    proposal_id TEXT NOT NULL REFERENCES task_proposals(id) ON DELETE CASCADE,
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    rolled_back_at TEXT
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                """
            )
            project_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(projects)").fetchall()
            }
            for name in ("mount_id", "host_path", "container_path"):
                if name not in project_columns:
                    connection.execute(f"ALTER TABLE projects ADD COLUMN {name} TEXT")
            connection.execute(
                "UPDATE projects SET container_path=root_path WHERE container_path IS NULL"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_mount_id "
                "ON projects(mount_id) WHERE mount_id IS NOT NULL"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_container_path "
                "ON projects(container_path) WHERE container_path IS NOT NULL"
            )
            now = utc_now()
            connection.execute(
                "INSERT OR IGNORE INTO local_users(id, role, created_at) VALUES (?, ?, ?)",
                ("local-user", "owner", now),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, now),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (2, now),
            )
            connection.commit()
        finally:
            connection.close()

    def _one(self, sql: str, params: Sequence[object] = ()) -> dict[str, Any] | None:
        connection = self.connect()
        try:
            row = connection.execute(sql, tuple(params)).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    def _all(self, sql: str, params: Sequence[object] = ()) -> list[dict[str, Any]]:
        connection = self.connect()
        try:
            return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]
        finally:
            connection.close()

    def upsert_project(
        self,
        root_path: str | Path,
        *,
        name: str | None = None,
        default_model: str | None = None,
        default_mode: str = "review",
        mount_id: str | None = None,
        host_path: str | None = None,
        container_path: str | Path | None = None,
    ) -> dict[str, Any]:
        root = str(Path(root_path).expanduser().resolve())
        container = str(Path(container_path or root).expanduser().resolve())
        if container != root:
            raise ValueError("Project root and container path must identify the same directory.")
        now = utc_now()
        existing = self.get_project_by_root(root)
        if existing:
            with self.transaction() as connection:
                connection.execute(
                    """UPDATE projects SET name=?, updated_at=?, last_opened_at=?, is_archived=0,
                       default_model=COALESCE(?, default_model), default_mode=?,
                       mount_id=COALESCE(?, mount_id), host_path=COALESCE(?, host_path),
                       container_path=? WHERE id=?""",
                    (
                        name or existing["name"],
                        now,
                        now,
                        default_model,
                        default_mode,
                        mount_id,
                        host_path,
                        container,
                        existing["id"],
                    ),
                )
            return self.get_project(str(existing["id"])) or existing
        project_id = new_id("project")
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO projects(
                    id, name, root_path, created_at, updated_at, last_opened_at,
                    default_model, default_mode, mount_id, host_path, container_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    name or Path(root).name or root,
                    root,
                    now,
                    now,
                    now,
                    default_model,
                    default_mode,
                    mount_id,
                    host_path,
                    container,
                ),
            )
        return self.get_project(project_id) or {}

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM projects WHERE id=?", (project_id,))

    def get_project_by_root(self, root_path: str | Path) -> dict[str, Any] | None:
        root = str(Path(root_path).expanduser().resolve())
        return self._one("SELECT * FROM projects WHERE root_path=?", (root,))

    def get_project_by_mount_id(self, mount_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM projects WHERE mount_id=?", (mount_id,))

    def list_projects(
        self, *, include_archived: bool = False, search: str = ""
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[object] = []
        if not include_archived:
            clauses.append("p.is_archived=0")
        if search:
            clauses.append("(p.name LIKE ? OR p.root_path LIKE ?)")
            pattern = f"%{search}%"
            params.extend((pattern, pattern))
        return self._all(
            f"""SELECT p.*,
                (SELECT title FROM tasks t WHERE t.project_id=p.id ORDER BY t.updated_at DESC LIMIT 1)
                AS last_task_title
                FROM projects p WHERE {" AND ".join(clauses)}
                ORDER BY p.last_opened_at DESC""",
            params,
        )

    def open_project(self, project_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE projects SET last_opened_at=?, updated_at=?, is_archived=0 WHERE id=?",
                (now, now, project_id),
            )
            if cursor.rowcount == 0:
                return None
            connection.execute(
                "INSERT OR REPLACE INTO settings(key, value_json) VALUES ('active_project_id', ?)",
                (json.dumps(project_id),),
            )
        return self.get_project(project_id)

    def archive_project(self, project_id: str) -> bool:
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE projects SET is_archived=1, updated_at=? WHERE id=?",
                (utc_now(), project_id),
            )
        return cursor.rowcount > 0

    def create_task(
        self,
        *,
        task_id: str,
        project_id: str,
        title: str,
        user_message: str,
        status: str,
        mode: str,
        provider: str,
        model: str,
        parent_task_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO tasks(
                    id, project_id, parent_task_id, title, user_message, status, mode,
                    provider, model, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    project_id,
                    parent_task_id,
                    title,
                    user_message,
                    status,
                    mode,
                    provider,
                    model,
                    now,
                    now,
                ),
            )
        return self.get_task(task_id) or {}

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM tasks WHERE id=?", (task_id,))

    def list_tasks(self, project_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY updated_at DESC LIMIT ?",
            (project_id, limit),
        )

    def update_task(self, task_id: str, **values: object) -> dict[str, Any] | None:
        allowed = {"title", "status", "mode", "provider", "model", "completed_at", "fix_iteration"}
        fields = {key: value for key, value in values.items() if key in allowed}
        if not fields:
            return self.get_task(task_id)
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key}=?" for key in fields)
        with self.transaction() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id=?",
                (*fields.values(), task_id),
            )
        return self.get_task(task_id)

    def add_message(self, task_id: str, role: str, content: str) -> dict[str, Any]:
        message_id = new_id("message")
        now = utc_now()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO task_messages(id, task_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (message_id, task_id, role, content, now),
            )
        return {
            "id": message_id,
            "task_id": task_id,
            "role": role,
            "content": content,
            "created_at": now,
        }

    def list_messages(self, task_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM task_messages WHERE task_id=? ORDER BY created_at, rowid", (task_id,)
        )

    def add_plan(self, task_id: str, plan_id: str, plan: Mapping[str, Any]) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO task_plans(id, task_id, plan_json, created_at) VALUES (?, ?, ?, ?)",
                (plan_id, task_id, json.dumps(plan, ensure_ascii=False), utc_now()),
            )

    def latest_plan(self, task_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM task_plans WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (task_id,),
        )
        if row:
            row["plan"] = json.loads(str(row["plan_json"]))
        return row

    def add_proposal(self, task_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        proposal_id = str(values.get("id") or new_id("proposal"))
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO task_proposals(
                    id, task_id, proposed_diff, changed_files_json, summary, status, step_id,
                    action, skill_name, fix_iteration, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    proposal_id,
                    task_id,
                    str(values.get("proposed_diff", "")),
                    json.dumps(values.get("changed_files", []), ensure_ascii=False),
                    str(values.get("summary", "")),
                    str(values.get("status", "waiting_approval")),
                    str(values.get("step_id", "")),
                    str(values.get("action", "apply_patch")),
                    values.get("skill_name"),
                    int(values.get("fix_iteration", 0)),
                    utc_now(),
                ),
            )
        return self.get_proposal(proposal_id) or {}

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM task_proposals WHERE id=?", (proposal_id,))
        return self._decode_proposal(row)

    def latest_proposal(self, task_id: str, *, applied_only: bool = False) -> dict[str, Any] | None:
        clause = (
            " AND snapshot_id IS NOT NULL AND rolled_back_at IS NULL"
            " AND (applied_at IS NOT NULL OR status='failed')"
            if applied_only
            else ""
        )
        row = self._one(
            f"SELECT * FROM task_proposals WHERE task_id=?{clause} ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (task_id,),
        )
        return self._decode_proposal(row)

    @staticmethod
    def _decode_proposal(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row:
            row["changed_files"] = json.loads(str(row["changed_files_json"]))
        return row

    def update_proposal(self, proposal_id: str, **values: object) -> dict[str, Any] | None:
        allowed = {"status", "applied_at", "rolled_back_at", "snapshot_id"}
        fields = {key: value for key, value in values.items() if key in allowed}
        if fields:
            assignments = ", ".join(f"{key}=?" for key in fields)
            with self.transaction() as connection:
                connection.execute(
                    f"UPDATE task_proposals SET {assignments} WHERE id=?",
                    (*fields.values(), proposal_id),
                )
        return self.get_proposal(proposal_id)

    def add_approval(self, task_id: str, step_id: str, action: str, status: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO task_approvals(id, task_id, step_id, action, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id("approval"), task_id, step_id, action, status, utc_now()),
            )

    def approval_status(self, task_id: str, step_id: str, action: str) -> str | None:
        row = self._one(
            """SELECT status FROM task_approvals WHERE task_id=? AND step_id=? AND action=?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (task_id, step_id, action),
        )
        return str(row["status"]) if row else None

    def add_run(
        self,
        task_id: str,
        *,
        status: str,
        verification_command: str,
        verification_argv: Sequence[str],
        verification_output: str,
        report: str,
    ) -> dict[str, Any]:
        run_id = new_id("run")
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO task_runs(
                    id, task_id, status, verification_command, verification_argv_json,
                    verification_output, report, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    task_id,
                    status,
                    verification_command,
                    json.dumps(list(verification_argv)),
                    verification_output,
                    report,
                    utc_now(),
                ),
            )
        return self.latest_run(task_id) or {}

    def latest_run(self, task_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM task_runs WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (task_id,),
        )
        if row:
            row["verification_argv"] = json.loads(str(row["verification_argv_json"]))
        return row

    def add_snapshot(self, task_id: str, proposal_id: str, manifest: Mapping[str, Any]) -> str:
        snapshot_id = new_id("snapshot")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO task_snapshots(id, task_id, proposal_id, manifest_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    task_id,
                    proposal_id,
                    json.dumps(manifest, ensure_ascii=False),
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE task_proposals SET snapshot_id=? WHERE id=?", (snapshot_id, proposal_id)
            )
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM task_snapshots WHERE id=?", (snapshot_id,))
        if row:
            row["manifest"] = json.loads(str(row["manifest_json"]))
        return row

    def mark_snapshot_rolled_back(self, snapshot_id: str, proposal_id: str) -> None:
        now = utc_now()
        with self.transaction() as connection:
            connection.execute(
                "UPDATE task_snapshots SET rolled_back_at=? WHERE id=?", (now, snapshot_id)
            )
            connection.execute(
                "UPDATE task_proposals SET rolled_back_at=?, status='rolled_back' WHERE id=?",
                (now, proposal_id),
            )

    def add_event(self, task_id: str, event: Mapping[str, Any]) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO task_events(id, task_id, event_json, created_at) VALUES (?, ?, ?, ?)",
                (new_id("event"), task_id, json.dumps(event, ensure_ascii=False), utc_now()),
            )

    def list_events(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM task_events WHERE task_id=? ORDER BY created_at, rowid", (task_id,)
        )
        return [json.loads(str(row["event_json"])) for row in rows]

    def get_settings(self) -> dict[str, Any]:
        return {
            str(row["key"]): json.loads(str(row["value_json"]))
            for row in self._all("SELECT key, value_json FROM settings")
        }

    def set_settings(self, values: Mapping[str, Any]) -> dict[str, Any]:
        with self.transaction() as connection:
            for key, value in values.items():
                connection.execute(
                    "INSERT OR REPLACE INTO settings(key, value_json) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
        return self.get_settings()
