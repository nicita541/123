from __future__ import annotations


class RollbackManager:
    def create_checkpoint(self) -> None:
        return None

    def rollback(self) -> None:
        raise NotImplementedError("Rollback is not implemented in MVP.")

