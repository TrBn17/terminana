"""
ai_skills/src/system_tools.py
─────────────────────────────
Demo: viết tool mới chỉ cần gắn @tool → chạy generate → có JSON ngay.
"""

from __future__ import annotations

import platform
from datetime import datetime
from typing import Any

from terminana.tools.decorator import tool


@tool
def get_system_info(sections: str = "all") -> dict[str, Any]:
    """Get current system information including OS, Python version, time.

    sections : Which info sections to include: 'all', 'os', 'python', 'time'. Default 'all'.
    """
    info: dict[str, Any] = {}

    if sections in ("all", "os"):
        info["os"] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        }

    if sections in ("all", "python"):
        info["python"] = {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        }

    if sections in ("all", "time"):
        now = datetime.now()
        info["time"] = {
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": int(now.timestamp()),
        }

    return {"success": True, **info}


@tool(name="calculate")
def evaluate_expression(expression: str) -> dict[str, Any]:
    """Safely evaluate a math expression and return the result.

    expression : A mathematical expression to evaluate, e.g. '2 ** 10 + 5 * 3'.
    """
    # Chỉ cho phép ký tự an toàn
    allowed = set("0123456789+-*/.() %,eE")
    if not all(c in allowed for c in expression.replace(" ", "")):
        return {"success": False, "error": "Expression contains unsafe characters."}

    try:
        result = eval(expression)  # noqa: S307 – safe vì đã filter
        return {"success": True, "expression": expression, "result": result}
    except Exception as exc:
        return {"success": False, "expression": expression, "error": str(exc)}
