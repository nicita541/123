from __future__ import annotations

from complex_agent.app import AgentRuntime
from complex_agent.core.modes import AgentMode
from complex_agent.ui.console_renderer import ConsoleRenderer


class InteractiveSession:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self.renderer = ConsoleRenderer()

    def run(self) -> None:
        while True:
            command = input("> ").strip()
            if command in {"abort", "exit", "quit"}:
                return
            if command.startswith("plan "):
                _, plan = self.runtime.plan(command[5:], mode=AgentMode.PLAN)
                print(self.renderer.render_plan(plan))
            elif command.startswith("run "):
                state = self.runtime.run(command[4:], mode=AgentMode.REVIEW)
                print(self.renderer.render_state(state))
            else:
                print("Commands: plan <task>, run <task>, abort")

