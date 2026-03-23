"""
ai_skills/chat/setup.py
───────────────────────
Thiết lập tương tác: chọn nhà cung cấp, lấy thông tin xác thực, tải danh sách mô hình từ API.

Public API
──────────
setup() -> (provider, model, auth, tools)
"""
from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any

import questionary
from questionary import Style
from rich.console import Console

from terminana.auth import get_openai_oauth_state, has_stored_openai_oauth, login_openai_chatgpt
from terminana.config.settings import DEFAULT_TIMEOUT, OPENAI_OAUTH_MODELS, PROVIDERS, get_api_key

console = Console()

# Kiểu hiển thị cho questionary, đồng bộ với bảng màu của Terminana.
_STYLE = Style([
    ("qmark",        "fg:#00d7ff bold"),
    ("question",     "fg:#ffffff bold"),
    ("answer",       "fg:#00d7ff bold"),
    ("pointer",      "fg:#00d7ff bold"),
    ("highlighted",  "fg:#00d7ff bold"),
    ("selected",     "fg:#00d7ff"),
    ("instruction",  "fg:#555555"),
])

def _fetch_models(provider: str, auth: Any) -> list[str]:
    """Lấy danh sách mô hình trực tiếp từ REST API, không đi qua SDK."""
    if provider == "gemini":
        api_key = str(auth)
        url  = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={api_key}&pageSize=200"
        )
        data = json.loads(urllib.request.urlopen(url, timeout=DEFAULT_TIMEOUT).read())
        return [
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
    if isinstance(auth, dict) and auth.get("type") == "openai_oauth":
        return OPENAI_OAUTH_MODELS[:]

    api_key = str(auth)
    req  = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT).read())
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
    """Hộp chọn công cụ, dùng phím cách để bật/tắt và Enter để xác nhận."""
    from terminana.tools import TOOL_DEFINITIONS

    choices = [
        questionary.Choice(
            title=f"{t['name']}  {t['description'][:60]}",
            value=t["name"],
            checked=True,
        )
        for t in TOOL_DEFINITIONS
    ]
    selected = questionary.checkbox(
        "Chọn công cụ cho AI (phím cách bật/tắt, Enter xác nhận)",
        choices=choices,
        style=_STYLE,
    ).ask()
    if selected is None:           # Ctrl+C
        sys.exit(0)
    return selected


def resolve_auth(provider: str) -> Any:
    if provider != "openai":
        return get_api_key(provider)

    choices: list[questionary.Choice] = []
    if has_stored_openai_oauth():
        choices.append(questionary.Choice("Dùng đăng nhập ChatGPT đã lưu", value="oauth_saved"))
    choices.extend([
        questionary.Choice("Đăng nhập ChatGPT bằng OAuth", value="oauth_login"),
        questionary.Choice("Nhập OpenAI API key", value="api_key"),
    ])

    method = questionary.select(
        "Chọn cách xác thực OpenAI",
        choices=choices,
        style=_STYLE,
        use_shortcuts=False,
        use_arrow_keys=True,
    ).ask()
    if method is None:
        sys.exit(0)

    if method == "oauth_saved":
        try:
            state = get_openai_oauth_state(force_refresh=True)
            return {
                "type": "openai_oauth",
                "access_token": state.session_access_token,
                "account_id": state.account_id or "",
                "email": state.email or "",
            }
        except Exception as exc:
            console.print(f"  [yellow]Thông tin OAuth đã lưu hiện không dùng được:[/] {exc}")
            console.print("  [dim]Đang yêu cầu đăng nhập ChatGPT lại...[/]")
            login_openai_chatgpt()
            state = get_openai_oauth_state(force_refresh=False)
            return {
                "type": "openai_oauth",
                "access_token": state.session_access_token,
                "account_id": state.account_id or "",
                "email": state.email or "",
            }
    if method == "oauth_login":
        login_openai_chatgpt()
        state = get_openai_oauth_state(force_refresh=False)
        return {
            "type": "openai_oauth",
            "access_token": state.session_access_token,
            "account_id": state.account_id or "",
            "email": state.email or "",
        }
    return get_api_key(provider)


def setup() -> tuple[str, str, Any, list[str]]:
    """
    Chạy interactive setup từ terminal.
    Trả về (provider, model, auth, enabled_tools).
    """
    provider = pick("Chọn nhà cung cấp", list(PROVIDERS))
    auth     = resolve_auth(provider)

    console.print("  [dim]Đang tải danh sách mô hình...[/]")
    models = _fetch_models(provider, auth)

    model         = pick(f"Chọn mô hình [{provider.upper()}]", models)
    enabled_tools = pick_tools()
    return provider, model, auth, enabled_tools
