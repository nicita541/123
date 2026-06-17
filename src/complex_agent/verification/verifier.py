from __future__ import annotations

from dataclasses import dataclass, field

from complex_agent.core.agent_state import AgentState
from complex_agent.safety.safety_policy import SafetyPolicy


@dataclass(slots=True)
class VerificationResult:
    success: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Verifier:
    def __init__(self, safety: SafetyPolicy | None = None) -> None:
        self.safety = safety

    def verify_state(
        self,
        state: AgentState,
        *,
        final_report_text: str | None = None,
    ) -> VerificationResult:
        errors = list(dict.fromkeys(state.errors))
        warnings = list(state.warnings)
        if not state.observations:
            warnings.append("No tool observations were recorded.")
        for observation in state.observations:
            if not observation.success:
                message = observation.error or (
                    f"Observation failed: {observation.source} - "
                    f"{observation.summary or observation.content[:80]}"
                )
                _append_once(errors, message)
            if observation.source in {"shell", "build", "test_runner", "lint"} and not observation.success:
                _append_once(errors, f"{observation.source} observation failed.")

        if state.changed_files:
            approved_mutation = any(
                observation.metadata.get("mutation_approved") is True
                for observation in state.observations
            )
            if not approved_mutation:
                _append_once(errors, "Changed files were recorded without approved mutation metadata.")

        if self.safety:
            for changed_file in state.changed_files:
                allowed, reason = self.safety.file_guard.validate_write(changed_file)
                if not allowed:
                    _append_once(errors, f"Changed file is forbidden: {changed_file} ({reason})")

        if errors and final_report_text is not None:
            normalized_report = final_report_text.lower()
            if "error" not in normalized_report and "ошиб" not in normalized_report:
                _append_once(errors, "Final report does not visibly report existing errors.")
        return VerificationResult(success=not errors, warnings=warnings, errors=errors)


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
