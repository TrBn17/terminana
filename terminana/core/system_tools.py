"""Core utilities for safe system inspection and arithmetic evaluation."""

from __future__ import annotations

import ast
import operator
import platform
from collections.abc import Callable
from datetime import datetime
from typing import Any

from terminana.tools.decorator import tool

_VALID_SECTIONS = {"all", "os", "python", "time"}
_MAX_EXPRESSION_LENGTH = 200
_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate_math_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Expression):
        return _evaluate_math_node(node.body)

    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value

    if isinstance(node, ast.BinOp):
        operator_fn = _BINARY_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise ValueError("Unsupported operator.")
        return operator_fn(_evaluate_math_node(node.left), _evaluate_math_node(node.right))

    if isinstance(node, ast.UnaryOp):
        operator_fn = _UNARY_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise ValueError("Unsupported unary operator.")
        return operator_fn(_evaluate_math_node(node.operand))

    raise ValueError("Only basic arithmetic expressions are allowed.")


@tool
def get_system_info(sections: str = "all") -> dict[str, Any]:
    """Get current system information for the requested section."""
    normalized_section = sections.strip().lower()
    if normalized_section not in _VALID_SECTIONS:
        return {
            "success": False,
            "error": f"Unsupported section: {sections!r}.",
            "allowed_sections": sorted(_VALID_SECTIONS),
        }

    info: dict[str, Any] = {}

    if normalized_section in ("all", "os"):
        info["os"] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        }

    if normalized_section in ("all", "python"):
        info["python"] = {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        }

    if normalized_section in ("all", "time"):
        now = datetime.now().astimezone()
        info["time"] = {
            "datetime": now.isoformat(timespec="seconds"),
            "timestamp": int(now.timestamp()),
        }

    return {"success": True, **info}


@tool(name="calculate")
def evaluate_expression(expression: str) -> dict[str, Any]:
    """Safely evaluate a basic arithmetic expression."""
    if not expression.strip():
        return {"success": False, "expression": expression, "error": "Expression cannot be empty."}

    if len(expression) > _MAX_EXPRESSION_LENGTH:
        return {
            "success": False,
            "expression": expression,
            "error": f"Expression is too long (max {_MAX_EXPRESSION_LENGTH} characters).",
        }

    try:
        parsed = ast.parse(expression, mode="eval")
        result = _evaluate_math_node(parsed)
        return {"success": True, "expression": expression, "result": result}
    except Exception as exc:
        return {"success": False, "expression": expression, "error": str(exc)}
