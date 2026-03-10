"""
ai_skills/tools/decorator.py
─────────────────────────────
Decorator ``@tool`` – gắn lên bất kỳ function Python nào để biến nó thành
AI tool. JSON definition được tự động sinh từ:

    1. Type hints   → parameters JSON Schema
    2. Docstring    → description (dòng đầu)
    3. Tên function → name (hoặc custom name)

Usage
-----
::

    from ai_skills.tools.decorator import tool

    @tool
    def greet(name: str, excited: bool = False) -> dict:
        \"\"\"Chào người dùng theo tên.\"\"\"
        msg = f"Xin chào, {name}!"
        if excited:
            msg = msg.upper()
        return {"success": True, "message": msg}

    # Hoặc custom name:
    @tool(name="search_web")
    def _internal_search(query: str, max_results: int = 5) -> dict:
        \"\"\"Tìm kiếm web.\"\"\"
        ...

Sau đó chạy:
    python -m ai_skills.tools.generate

→ Tự động sinh JSON vào ai_skills/tools/
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

# ── Registry toàn cục – decorator đẩy function vào đây ──────────────────
_TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


# ── Type mapping: Python type → JSON Schema type ─────────────────────────
_TYPE_MAP: dict[type, str] = {
    str:   "string",
    int:   "integer",
    float: "number",
    bool:  "boolean",
    list:  "array",
    dict:  "object",
}


def _python_type_to_json(py_type: type) -> str:
    """Chuyển Python type hint sang JSON Schema type string."""
    # Handle Optional, Union, etc.
    origin = getattr(py_type, "__origin__", None)
    if origin is not None:
        # list[...] → "array", dict[...] → "object"
        return _TYPE_MAP.get(origin, "string")
    return _TYPE_MAP.get(py_type, "string")


def _extract_param_descriptions(docstring: str) -> dict[str, str]:
    """
    Trích mô tả từng param từ docstring.
    Hỗ trợ format:
        param_name : mô tả ở đây
        param_name: mô tả ở đây
    """
    descriptions: dict[str, str] = {}
    if not docstring:
        return descriptions

    lines = docstring.split("\n")
    current_param = None
    current_desc: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Dạng "param_name : description" hoặc "param_name: desc"
        if ":" in stripped and not stripped.startswith(":"):
            parts = stripped.split(":", 1)
            candidate = parts[0].strip().split()[-1]  # lấy từ cuối trước ':'
            # Kiểm tra xem có phải tên param hợp lệ không
            if candidate.isidentifier() and len(parts) > 1 and parts[1].strip():
                if current_param:
                    descriptions[current_param] = " ".join(current_desc).strip()
                current_param = candidate
                current_desc = [parts[1].strip()]
                continue
        if current_param and stripped:
            current_desc.append(stripped)

    if current_param:
        descriptions[current_param] = " ".join(current_desc).strip()

    return descriptions


def _build_tool_definition(fn: Callable, custom_name: str | None = None) -> dict:
    """
    Đọc function signature + docstring → sinh tool definition dict.

    Output format (chuẩn JSON schema cho Gemini function calling):
    {
        "name":        "tool_name",
        "description": "Mô tả tool",
        "module":      "ai_skills.src.xxx",
        "function":    "function_name",
        "parameters":  { JSON Schema }
    }
    """
    name = custom_name or fn.__name__
    module = fn.__module__

    # ── Description từ docstring (dòng đầu) ──────────────────────────────
    doc = inspect.getdoc(fn) or f"Tool {name}"
    description = doc.split("\n")[0].strip()

    # ── Parameters từ type hints + defaults ──────────────────────────────
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    param_docs = _extract_param_descriptions(doc)

    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Bỏ qua 'return'
        if param_name in ("self", "cls"):
            continue

        py_type = hints.get(param_name, str)
        json_type = _python_type_to_json(py_type)

        prop: dict[str, Any] = {"type": json_type}

        # Mô tả param
        if param_name in param_docs:
            prop["description"] = param_docs[param_name]

        # Default value
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(param_name)

        # Handle list[dict] cho interactions-style params
        if json_type == "array":
            args = getattr(py_type, "__args__", None)
            if args:
                item_type = args[0]
                if item_type is dict or getattr(item_type, "__origin__", None) is dict:
                    prop["items"] = {"type": "object"}
                else:
                    prop["items"] = {"type": _python_type_to_json(item_type)}

        properties[param_name] = prop

    parameters = {
        "type": "object",
        "properties": properties,
    }
    if required:
        parameters["required"] = required

    return {
        "name": name,
        "description": description,
        "module": module,
        "function": fn.__name__,
        "parameters": parameters,
    }


# ─────────────────────────────────────────────────────────────────────────
# @tool decorator
# ─────────────────────────────────────────────────────────────────────────

def tool(fn: Callable | None = None, *, name: str | None = None) -> Callable:
    """
    Decorator đăng ký function thành AI tool.

    Dùng được 2 cách:

        @tool
        def my_func(...): ...

        @tool(name="custom_name")
        def my_func(...): ...
    """
    def _register(f: Callable) -> Callable:
        defn = _build_tool_definition(f, custom_name=name)
        tool_name = defn["name"]
        _TOOL_REGISTRY[tool_name] = defn
        # Gắn metadata lên function để truy cập nhanh
        f._tool_definition = defn  # type: ignore[attr-defined]
        f._tool_name = tool_name   # type: ignore[attr-defined]
        return f

    if fn is not None:
        # @tool (không có param)
        return _register(fn)
    else:
        # @tool(name="...")
        return _register


def get_registry() -> dict[str, dict]:
    """Trả về registry hiện tại (sau khi các module đã import)."""
    return dict(_TOOL_REGISTRY)
