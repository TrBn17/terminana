"""
ai_skills/tools/__init__.py
───────────────────────────
Plugin registry – JSON là single source of truth.

Mỗi tool được khai báo bằng 1 file JSON trong thư mục này:
{
    "name":        "run_command",
    "description": "...",
    "module":      "ai_skills.src.pexpect_tools",   ← module chứa logic
    "function":    "run_command",                    ← tên function (mặc định = name)
    "parameters":  { ... }                           ← JSON Schema cho AI
}

Dispatcher dùng importlib để tự động tìm và gọi function.
AI consumer chỉ cần:
    from ai_skills.tools import TOOL_DEFINITIONS, execute_tool

Thêm tool mới = 1 file JSON + 1 function Python. Không cần sửa code nào khác.

Public API
──────────
TOOL_DEFINITIONS          – list[dict], tất cả tools (load lúc import)
load_tools()              – (re)load danh sách từ tools.json
get_tool(name)            – lấy 1 tool definition theo tên
list_tool_names()         – danh sách tên tools
load_tool_file(name)      – đọc file JSON riêng lẻ
get_tool_definitions()    – chỉ trả về phần AI cần (name, description, parameters)
execute_tool(name, args)  – dynamic dispatch: JSON → importlib → function call
"""

from __future__ import annotations

import json
import importlib
from pathlib import Path
from typing import Any

_TOOLS_DIR  = Path(__file__).parent / "json"
_TOOLS_JSON = _TOOLS_DIR / "tools.json"

# ── Cache: {tool_name: callable} – lazy-loaded khi execute_tool lần đầu ──
_FUNCTION_CACHE: dict[str, Any] = {}


# ─────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────

def load_tools() -> list[dict]:
    """Đọc toàn bộ tools từ tools.json."""
    with _TOOLS_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def load_tool_file(name: str) -> dict:
    """Đọc file JSON riêng lẻ (vd: run_command.json)."""
    path = _TOOLS_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_tool(name: str) -> dict | None:
    """Tìm tool theo tên. Trả None nếu không có."""
    return next((t for t in TOOL_DEFINITIONS if t["name"] == name), None)


def list_tool_names() -> list[str]:
    """Danh sách tên tools."""
    return [t["name"] for t in TOOL_DEFINITIONS]


def get_tool_definitions(enabled: list[str] | None = None) -> list[dict]:
    """
    Trả về danh sách tools chỉ gồm 3 field AI cần:
    name, description, parameters (không có module/function).
    Dùng trực tiếp cho Gemini FunctionDeclaration.

    Parameters
    ----------
    enabled : danh sach ten tools muon bat. None = tat ca.
    """
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        }
        for t in TOOL_DEFINITIONS
        if enabled is None or t["name"] in enabled
    ]


# ─────────────────────────────────────────────────────────────────────────
# Dynamic dispatcher
# ─────────────────────────────────────────────────────────────────────────

def _resolve_function(tool_def: dict):
    """
    Từ JSON definition, dùng importlib tìm ra Python callable.

    JSON cần có:
        "module":   "ai_skills.src.pexpect_tools"
        "function": "run_command"   (nếu không có, dùng "name")

    Kết quả được cache lại để không import lại mỗi lần gọi.
    """
    name     = tool_def["name"]
    mod_path = tool_def["module"]
    fn_name  = tool_def.get("function", name)   # fallback về name

    if name in _FUNCTION_CACHE:
        return _FUNCTION_CACHE[name]

    # importlib.import_module tự tìm module trong sys.path
    module   = importlib.import_module(mod_path)
    fn       = getattr(module, fn_name)

    _FUNCTION_CACHE[name] = fn
    return fn


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Dynamic dispatcher – AI gọi tool bằng tên, dispatcher tự phân giải.

    Flow:
        1. Tra tools.json → tìm tool definition theo name
        2. Đọc "module" + "function" từ JSON
        3. importlib.import_module(module)
        4. getattr(module, function)
        5. Gọi function(**args) → trả kết quả

    Nếu tool không tồn tại hoặc module/function lỗi → trả {"success": False, "error": ...}
    """
    tool_def = get_tool(name)
    if tool_def is None:
        return {"success": False, "error": f"Unknown tool: '{name}'. Available: {list_tool_names()}"}

    try:
        fn = _resolve_function(tool_def)
    except (ImportError, AttributeError) as exc:
        return {
            "success": False,
            "error": f"Cannot load tool '{name}': {exc}",
            "module": tool_def.get("module"),
            "function": tool_def.get("function", name),
        }

    try:
        return fn(**args)
    except TypeError as exc:
        return {"success": False, "error": f"Bad arguments for '{name}': {exc}"}
    except Exception as exc:
        return {"success": False, "error": f"Tool '{name}' failed: {exc}"}


# ─────────────────────────────────────────────────────────────────────────
# Auto-load khi import package
# ─────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = load_tools()

