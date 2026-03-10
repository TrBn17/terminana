"""
ai_skills/chat/setup.py
───────────────────────
Interactive setup: chọn provider, lấy API key, fetch models từ API.

Public API
──────────
setup() -> (provider, model, api_key)
"""
from __future__ import annotations

import json
import sys
import urllib.request

import questionary
from questionary import Style
from rich.console import Console

from terminana.config.settings import PROVIDERS, get_api_key

console = Console()

# Style cho questionary: khớp với màu Terminana
_STYLE = Style([
    ("qmark",        "fg:#00d7ff bold"),
    ("question",     "fg:#ffffff bold"),
    ("answer",       "fg:#00d7ff bold"),
    ("pointer",      "fg:#00d7ff bold"),
    ("highlighted",  "fg:#00d7ff bold"),
    ("selected",     "fg:#00d7ff"),
    ("instruction",  "fg:#555555"),
])


def _fetch_models(provider: str, api_key: str) -> list[str]:
    """Lấy danh sách models trực tiếp từ REST API — không dùng SDK."""
    if provider == "gemini":
        url  = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={api_key}&pageSize=200"
        )
        data = json.loads(urllib.request.urlopen(url).read())
        return [
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
    req  = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    data = json.loads(urllib.request.urlopen(req).read())
    return sorted(m["id"] for m in data.get("data", []) if m["id"].startswith("gpt"))


def pick(title: str, options: list[str]) -> str:
    """Menu cuộn với phím lên/xuống, Enter xác nhận."""
    result = questionary.select(
        title,
        choices=options,
        style=_STYLE,
        use_shortcuts=False,
        use_arrow_keys=True,
    ).ask()
    if result is None:           # Ctrl+C
        sys.exit(0)
    return result


def pick_tools() -> list[str]:
    """Checkbox chọn tools, Space bật/tắt, Enter xác nhận."""
    from terminana.tools import TOOL_DEFINITIONS

    choices = [
        questionary.Choice(
            title=f"{t['name']}  {t['description'][:60]}",
            value=t["name"],
            checked=True,          # mặc định bật hết
        )
        for t in TOOL_DEFINITIONS
    ]
    selected = questionary.checkbox(
        "Chọn tools cho AI (Space bật/tắt, Enter xác nhận)",
        choices=choices,
        style=_STYLE,
    ).ask()
    if selected is None:           # Ctrl+C
        sys.exit(0)
    return selected


def setup() -> tuple[str, str, str, list[str]]:
    """
    Chạy interactive setup từ terminal.
    Trả về (provider, model, api_key, enabled_tools).
    """
    provider = pick("Chọn nhà cung cấp", list(PROVIDERS))
    api_key  = get_api_key(provider)

    console.print("  [dim]Đang tải danh sách models...[/]")
    models = _fetch_models(provider, api_key)

    model         = pick(f"Chọn model [{provider.upper()}]", models)
    enabled_tools = pick_tools()
    return provider, model, api_key, enabled_tools
