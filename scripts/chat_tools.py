"""scripts/chat_tools.py — Gemini + tools, minimal agentic loop."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types
from terminana.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from terminana.tools import get_tool_definitions, execute_tool

# Gemini yêu cầu "type" uppercase; JSON Schema chuẩn dùng lowercase → upper hết
def _fix(d):
    if isinstance(d, dict):
        return {k: v.upper() if k == "type" else _fix(v) for k, v in d.items()}
    return [_fix(i) for i in d] if isinstance(d, list) else d

_decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
          parameters=types.Schema(**_fix(t["parameters"]))) for t in get_tool_definitions()]

client = genai.Client(api_key=GEMINI_API_KEY)
chat   = client.chats.create(
    model=GEMINI_MODEL,
    config=types.GenerateContentConfig(tools=[types.Tool(function_declarations=_decls)]),
)


def ask(prompt: str) -> str:
    resp = chat.send_message(prompt)
    while fc_parts := [p for p in resp.candidates[0].content.parts if p.function_call]:
        results = [
            types.Part.from_function_response(
                name=p.function_call.name,
                response={"result": execute_tool(p.function_call.name, dict(p.function_call.args))},
            ) for p in fc_parts
        ]
        resp = chat.send_message(results)
    return resp.text


if __name__ == "__main__":
    for q in [
        "Tính 2**10 + 5*3",
        "Python version hiện tại là gì?",
        "Chạy lệnh 'echo hello world' và cho biết kết quả",
    ]:
        print(f"\nQ: {q}")
        print(f"A: {ask(q)}")
