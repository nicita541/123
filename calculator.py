from __future__ import annotations

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
