from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode
from complex_agent.core.observation import Observation
from complex_agent.core.task import Task
from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.verification.verifier import Verifier


class VerifierTests(unittest.TestCase):
    def test_empty_state_warns_but_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = AgentState(Task.create("Check", mode=AgentMode.PLAN, project_path=temp))
            result = Verifier().verify_state(state)
            self.assertTrue(result.success)
            self.assertTrue(result.warnings)

    def test_failed_observation_without_error_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = AgentState(Task.create("Check", mode=AgentMode.PLAN, project_path=temp))
            state.observations.append(
                Observation(
                    source="read_file",
                    content="",
                    summary="read failed",
                    raw_output=None,
                    success=False,
                )
            )
            result = Verifier().verify_state(state)
            self.assertFalse(result.success)
            self.assertTrue(any("Observation failed" in error for error in result.errors))

    def test_failed_shell_build_and_test_observations_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for source in ["shell", "build", "test_runner"]:
                with self.subTest(source=source):
                    state = AgentState(Task.create("Check", mode=AgentMode.PLAN, project_path=temp))
                    state.observations.append(
                        Observation(
                            source=source,
                            content="failed",
                            summary="command failed",
                            raw_output=None,
                            success=False,
                        )
                    )
                    result = Verifier().verify_state(state)
                    self.assertFalse(result.success)
                    self.assertTrue(any(source in error for error in result.errors))

    def test_forbidden_changed_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = AgentState(Task.create("Check", mode=AgentMode.REVIEW, project_path=root))
            state.changed_files.append(".env")
            state.observations.append(
                Observation(
                    source="apply_patch",
                    content="",
                    summary="patched",
                    raw_output=None,
                    success=True,
                    metadata={"mutation_approved": True},
                )
            )
            result = Verifier(SafetyPolicy(root)).verify_state(state)
            self.assertFalse(result.success)
            self.assertTrue(any("forbidden" in error.lower() for error in result.errors))

    def test_changed_file_without_approved_mutation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = AgentState(Task.create("Check", mode=AgentMode.REVIEW, project_path=root))
            state.changed_files.append("safe.txt")
            state.observations.append(
                Observation(
                    source="read_file",
                    content="",
                    summary="read",
                    raw_output=None,
                    success=True,
                )
            )
            result = Verifier(SafetyPolicy(root)).verify_state(state)
            self.assertFalse(result.success)
            self.assertTrue(any("approved mutation" in error for error in result.errors))

    def test_final_report_must_surface_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = AgentState(Task.create("Check", mode=AgentMode.PLAN, project_path=temp))
            state.errors.append("Something failed")
            result = Verifier().verify_state(state, final_report_text="Everything is fine.")
            self.assertFalse(result.success)
            self.assertTrue(any("Final report" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
