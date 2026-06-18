from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from complex_agent.core.modes import RiskLevel
from complex_agent.core.task import Task
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep


CALCULATOR_PATH = "calculator.py"


@dataclass(frozen=True, slots=True)
class CalculatorProposal:
    plan: Plan
    patch: str
    changed_files: list[str]
    summary: str


class PythonCalculatorSkill:
    name = "python_calculator"

    _markers = (
        "калькулятор",
        "консольный калькулятор",
        "calculator",
        "python calculator",
        "программа на python",
    )

    def supports(self, task_text: str) -> bool:
        normalized = task_text.lower()
        return any(marker in normalized for marker in self._markers) and (
            "python" in normalized or "питон" in normalized or "калькулятор" in normalized
        )

    def create_plan(self, task: Task, *, existing_content: str | None = None) -> Plan:
        steps = [
            PlanStep.create(
                type="analysis",
                description="Проанализировать задачу и подготовить безопасный план изменения.",
                required_tool="final_report",
                input={"message": task.normalized_goal},
            ),
            PlanStep.create(
                type="patch",
                description="Создать или обновить calculator.py через proposed patch.",
                required_tool="apply_patch",
                input={"path": CALCULATOR_PATH},
                risk_level=RiskLevel.HIGH,
                approval_required=True,
            ),
            PlanStep.create(
                type="implementation",
                description="Добавить операции +, -, *, / и обработку деления на ноль.",
                required_tool="apply_patch",
                input={"path": CALCULATOR_PATH},
                risk_level=RiskLevel.HIGH,
                approval_required=True,
            ),
            PlanStep.create(
                type="verification",
                description="Запустить self-test без интерактивного ввода.",
                required_tool="shell",
                input={"argv": ["python", "calculator.py", "--self-test"]},
                risk_level=RiskLevel.MEDIUM,
            ),
            PlanStep.create(
                type="report",
                description="Сформировать финальный отчёт с инструкциями запуска.",
                required_tool="final_report",
                input={"message": task.normalized_goal},
            ),
        ]
        plan = Plan.create(task_id=task.id, goal=task.normalized_goal, steps=steps)
        if existing_content:
            plan.risks.append("calculator.py уже существует и будет обновлён после подтверждения.")
        plan.approval_points.append("Запись calculator.py требует подтверждения пользователя.")
        return plan

    def propose(self, task: Task, project_root: Path) -> CalculatorProposal:
        target = project_root / CALCULATOR_PATH
        existing = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        desired = calculator_source()
        patch = _make_patch(existing, desired)
        return CalculatorProposal(
            plan=self.create_plan(task, existing_content=existing or None),
            patch=patch,
            changed_files=[CALCULATOR_PATH],
            summary="Будет создан или обновлён calculator.py и добавлен self-test.",
        )


def _make_patch(existing: str, desired: str) -> str:
    old_lines = existing.splitlines()
    new_lines = desired.splitlines()
    fromfile = f"a/{CALCULATOR_PATH}" if existing else "/dev/null"
    lines = unified_diff(
        old_lines,
        new_lines,
        fromfile=fromfile,
        tofile=f"b/{CALCULATOR_PATH}",
        lineterm="",
    )
    return "\n".join(lines) + "\n"


def calculator_source() -> str:
    return '''from __future__ import annotations

import argparse


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division by zero is not allowed.")
    return a / b


def calculate(a: float, b: float, operation: str) -> float:
    operations = {
        "+": add,
        "-": subtract,
        "*": multiply,
        "/": divide,
    }
    if operation not in operations:
        raise ValueError(f"Unsupported operation: {operation}")
    return operations[operation](a, b)


def run_self_test() -> None:
    assert add(2, 3) == 5
    assert subtract(7, 4) == 3
    assert multiply(6, 5) == 30
    assert divide(8, 2) == 4
    try:
        divide(1, 0)
    except ValueError as exc:
        assert "Division by zero" in str(exc)
    else:
        raise AssertionError("Division by zero did not raise ValueError.")
    print("OK: all calculator self-tests passed")


def interactive() -> None:
    print("Console calculator")
    print("Operations: +, -, *, /")
    while True:
        operation = input("Operation or q to quit: ").strip()
        if operation.lower() in {"q", "quit", "exit"}:
            print("Goodbye")
            return
        if operation not in {"+", "-", "*", "/"}:
            print("Unsupported operation.")
            continue
        try:
            a = float(input("First number: "))
            b = float(input("Second number: "))
            print(f"Result: {calculate(a, b, operation)}")
        except ValueError as exc:
            print(f"Error: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Console calculator")
    parser.add_argument("--self-test", action="store_true", help="Run calculator self-tests.")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return 0
    interactive()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
