from __future__ import annotations

from complex_agent.core.agent_state import AgentState
from complex_agent.storage.sqlite_store import SQLiteStore


class RunStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_state(self, state: AgentState) -> None:
        summary = state.final_result.summary if state.final_result else ""
        self.store.execute(
            """
            INSERT OR REPLACE INTO runs (id, mode, goal, status, created_at, summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                state.task.id,
                state.task.mode.value,
                state.task.normalized_goal,
                state.task.status.value,
                state.task.created_at.isoformat(),
                summary,
            ),
        )
        for observation in state.observations:
            self.store.execute(
                """
                INSERT INTO observations (run_id, source, success, summary, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    state.task.id,
                    observation.source,
                    1 if observation.success else 0,
                    observation.summary,
                    observation.error,
                ),
            )

    def list_runs(self, limit: int = 20) -> list[tuple[object, ...]]:
        return self.store.query(
            "SELECT id, mode, status, goal, summary FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

