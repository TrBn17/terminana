"""
scripts/test_tools.py
─────────────────────
Test script: dùng public API từ ai_skills.tools để gọi từng tool
được khai báo trong tools.json, in kết quả ra màn hình.

Chạy:
    python scripts/test_tools.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ── Đảm bảo project root trong sys.path ─────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Import public API của tools package ─────────────────────────────────
from terminana.tools import (       # noqa: E402
    execute_tool,
    get_tool_definitions,
    list_tool_names,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  TEST: {title}")
    print("=" * 60)


def _show(result: Any, indent: int = 2) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=indent, default=str))


# ── Test cases ───────────────────────────────────────────────────────────

def test_calculate() -> None:
    _section("calculate")
    cases = [
        ("2 ** 10 + 5 * 3",    True),
        ("3.14159 * 10 ** 2",  True),
        ("(100 - 32) * 5 / 9", True),   # Fahrenheit → Celsius
        ("1 + 'hack'",         False),  # unsafe chars → bị chặn
    ]
    for expr, expect_ok in cases:
        tag = "OK" if expect_ok else "BLOCKED"
        print(f"\n  [{tag}] expression: {expr!r}")
        result = execute_tool("calculate", {"expression": expr})
        _show(result)


def test_get_system_info() -> None:
    _section("get_system_info")
    for section in ("os", "python", "time", "all"):
        print(f"\n  sections={section!r}")
        result = execute_tool("get_system_info", {"sections": section})
        _show(result)


def test_run_command() -> None:
    _section("run_command")
    commands = [
        "python --version",
        "echo Hello from run_command!",
        "dir /b" if sys.platform == "win32" else "ls -1",
    ]
    for cmd in commands:
        print(f"\n  command: {cmd!r}")
        result = execute_tool("run_command", {"command": cmd, "timeout": 15})
        _show(result)


def test_spawn_and_interact() -> None:
    _section("spawn_and_interact")
    interactions = [
        {"expect": ">>>", "send": "1 + 1"},
        {"expect": "2",   "send": "exit()"},
        {"expect": None},               # chờ EOF
    ]
    print("\n  command: 'python -i -q'  (tính 1+1 rồi exit)")
    result = execute_tool(
        "spawn_and_interact",
        {
            "command": "python -i -q",
            "interactions": interactions,
            "timeout": 10,
        },
    )
    _show(result)


# ── Entry point ──────────────────────────────────────────────────────────

def main() -> None:
    print("=== AI Skills – Tool Test Runner ===")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"\nTools đã đăng ký ({len(list_tool_names())}):")
    for defn in get_tool_definitions():
        print(f"  • {defn['name']:25s}  {defn['description']}")

    test_calculate()
    test_get_system_info()
    test_run_command()
    test_spawn_and_interact()

    print("\n\nTất cả test hoàn thành!")


if __name__ == "__main__":
    main()
