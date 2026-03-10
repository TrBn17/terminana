"""
ai_skills/chat/session.py
─────────────────────────
Session factory: tạo ask-function cho một cuộc trò chuyện.
Không phụ thuộc vào UI (terminal hay Telegram dùng chung).

Public API
──────────
new_session(provider, api_key, model, on_tool) -> Callable[[str], str]
"""
from __future__ import annotations

import json
from typing import Any, Callable

from terminana.tools import get_tool_definitions, execute_tool

SYSTEM_PROMPT = (
    "Bạn là Terminana, trợ lý AI chạy trực tiếp trên máy tính của người dùng. "
    "Bạn có đầy đủ tools để tương tác với hệ thống cục bộ — hãy dùng chúng, "
    "đừng bao giờ nói rằng bạn không thể truy cập file hay hệ thống."
)


# ── Schema fix: JSON lowercase -> Gemini uppercase ────────────────────────
def _fix(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: v.upper() if k == "type" else _fix(v) for k, v in d.items()}
    return [_fix(i) for i in d] if isinstance(d, list) else d


# ── Gemini ────────────────────────────────────────────────────────────────
def _gemini_session(
    api_key: str,
    model: str,
    on_tool: Callable | None,
    enabled_tools: list[str] | None,
):
    from google import genai
    from google.genai import types

    defs  = get_tool_definitions(enabled_tools)
    decls = [
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=types.Schema(**_fix(t["parameters"])),
        )
        for t in defs
    ]
    client = genai.Client(api_key=api_key)   # giữ ref tránh GC đóng httpx
    chat   = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=decls)],
        ),
    )

    def ask(prompt: str) -> str:
        _alive = client  # giữ strong ref → ngăn GC thu hồi client → httpx không bị đóng
        resp = chat.send_message(prompt)
        while fc := [p for p in resp.candidates[0].content.parts if p.function_call]:
            results = []
            for p in fc:
                info   = f"[tool] {p.function_call.name}({dict(p.function_call.args)})"
                if on_tool:
                    on_tool(info)
                result = execute_tool(p.function_call.name, dict(p.function_call.args))
                results.append(
                    types.Part.from_function_response(
                        name=p.function_call.name,
                        response={"result": result},
                    )
                )
            resp = chat.send_message(results)
        return resp.text

    return ask


# ── OpenAI ────────────────────────────────────────────────────────────────
def _openai_session(
    api_key: str,
    model: str,
    on_tool: Callable | None,
    enabled_tools: list[str] | None,
):
    from openai import OpenAI

    tools = [
        {"type": "function", "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        }}
        for t in get_tool_definitions(enabled_tools)
    ]
    client  = OpenAI(api_key=api_key)
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def ask(prompt: str) -> str:
        history.append({"role": "user", "content": prompt})
        while True:
            msg = client.chat.completions.create(
                model=model, messages=history, tools=tools
            ).choices[0].message
            history.append(msg)
            if not msg.tool_calls:
                return msg.content
            for tc in msg.tool_calls:
                info   = f"[tool] {tc.function.name}({tc.function.arguments})"
                if on_tool:
                    on_tool(info)
                result = execute_tool(tc.function.name, json.loads(tc.function.arguments))
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

    return ask


# ── Factory ───────────────────────────────────────────────────────────────
def new_session(
    provider: str,
    api_key: str,
    model: str,
    on_tool: Callable[[str], None] | None = None,
    enabled_tools: list[str] | None = None,
) -> Callable[[str], str]:
    """
    Tạo ask-function cho một session.

    Parameters
    ----------
    provider      : "gemini" hoặc "openai"
    api_key       : API key tương ứng
    model         : tên model
    on_tool       : callback(info_str) mỗi khi AI gọi tool
    enabled_tools : danh sách tên tools được phép dùng. None = tất cả.
    """
    if provider == "gemini":
        return _gemini_session(api_key, model, on_tool, enabled_tools)
    if provider == "openai":
        return _openai_session(api_key, model, on_tool, enabled_tools)
    raise ValueError(f"Provider không hỗ trợ: {provider!r}")
