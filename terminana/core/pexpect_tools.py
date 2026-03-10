"""
Reusable pexpect-based tools designed for AI function-calling.

Sử dụng đúng API pexpect:
─────────────────────────
* pexpect.spawn          – dùng PTY thật (Linux/macOS)
* pexpect.popen_spawn.PopenSpawn – dùng subprocess.Popen (Windows, không cần PTY)
  Cả hai đều hỗ trợ cùng bộ API cốt lõi:
    child.expect(pattern | list)     → trả về index pattern khớp
    child.sendline(text)             → gửi text + \\n
    child.send(text)                 → gửi text không có \\n
    child.before                     → output TRƯỚC khi pattern khớp
    child.after                      → phần output ĐÃ KHỚP với pattern
    pexpect.EOF                      → sentinel – process kết thúc
    pexpect.TIMEOUT                  → sentinel – hết timeout

Public API
──────────
run_command(command, timeout)
    Chạy lệnh và thu thập output từng dòng qua vòng loop expect.

spawn_and_interact(command, interactions, timeout)
    Spawn process tương tác và đi qua chuỗi expect/sendline.
    Mỗi bước dùng expect([pattern, EOF, TIMEOUT]) để xử lý mọi tình huống.

TOOL_DEFINITIONS   – Gemini function declarations
execute_tool(name, args) – dispatcher
"""

from __future__ import annotations

import sys
import re
import io
from typing import Any

import pexpect
from pexpect import EOF, TIMEOUT  # sentinel objects của pexpect

from terminana.tools.decorator import tool

# ── Platform-aware child factory ──────────────────────────────────────────
if sys.platform == "win32":
    from pexpect.popen_spawn import PopenSpawn as _PopenSpawn
    _IS_WIN = True
else:
    _IS_WIN = False


def _strip_ansi(text: str) -> str:
    """Loại bỏ ANSI/VT100 escape sequences."""
    return re.sub(r"\x1b\[[0-9;]*[mGKHF]|\x1b\].*?\x07|\x1b[@-Z\\-_]", "", text)


def _make_child(command: str, timeout: int, log: io.StringIO | None = None):
    """
    Tạo pexpect child phù hợp với platform.

    - Windows: PopenSpawn (không dùng PTY, dùng subprocess.Popen)
    - Unix:    pexpect.spawn với /bin/bash -c (dùng PTY thật)

    Cả hai đều có chung API: expect(), sendline(), send(), before, after.
    """
    if _IS_WIN:
        child = _PopenSpawn(command, timeout=timeout, encoding="utf-8")
        if log is not None:
            child.logfile = log        # PopenSpawn: ghi tất cả I/O vào log
    else:
        child = pexpect.spawn(
            "/bin/bash", args=["-c", command],
            timeout=timeout, encoding="utf-8",
        )
        if log is not None:
            child.logfile_read = log   # spawn: chỉ ghi output từ child
    return child


# ─────────────────────────────────────────────────────────────────────────
# Tool 1 – run_command
#   Dùng vòng loop expect(['\n', EOF, TIMEOUT]) để thu từng dòng output,
#   thay vì chỉ gọi expect(EOF) một lần → đây là cách pexpect đề xuất để
#   streaming output.
# ─────────────────────────────────────────────────────────────────────────

@tool
def run_command(command: str, timeout: int = 30) -> dict[str, Any]:
    """Run a shell command on the host machine using pexpect and return the full captured output.

    command : The shell command to execute, e.g. 'dir' or 'python --version'.
    timeout : Maximum seconds to wait for the command to finish. Default 30.
    """
    # Tự động thêm "cmd /c" cho shell built-ins trên Windows
    _WIN_BUILTINS = {
        "dir", "echo", "type", "set", "cls", "copy", "del",
        "move", "ren", "md", "rd", "pushd", "popd",
    }
    run_cmd = command
    if _IS_WIN:
        first = command.strip().split()[0].lower() if command.strip() else ""
        if first in _WIN_BUILTINS:
            run_cmd = f"cmd /c {command}"

    log = io.StringIO()
    child = _make_child(run_cmd, timeout=timeout, log=log)

    lines: list[str] = []
    try:
        while True:
            # expect() trả về INDEX của pattern đầu tiên khớp trong danh sách
            idx = child.expect([r"\r\n", r"\n", EOF, TIMEOUT])

            # child.before = text thu được TRƯỚC khi pattern khớp
            fragment = _strip_ansi(child.before or "")
            if fragment:
                lines.append(fragment)

            if idx == 2:   # EOF – process kết thúc, thoát vòng lặp
                break
            if idx == 3:   # TIMEOUT
                return {
                    "success": False,
                    "command": command,
                    "error": f"Command timed out after {timeout}s.",
                    "partial_output": "\n".join(lines),
                }

    except Exception as exc:
        return {"success": False, "command": command, "error": str(exc)}

    return {"success": True, "command": command, "output": "\n".join(lines).strip()}


# ─────────────────────────────────────────────────────────────────────────
# Tool 2 – spawn_and_interact
#   Dùng expect([user_pattern, EOF, TIMEOUT]) tại mỗi bước để xử lý
#   cả ba tình huống: khớp đúng / process kết thúc sớm / timeout,
#   rồi sendline() để phản hồi. Đây là mô hình expect/response cốt lõi
#   của pexpect.
# ─────────────────────────────────────────────────────────────────────────

@tool
def spawn_and_interact(
    command: str,
    interactions: list[dict[str, str]],
    timeout: int = 30,
) -> dict[str, Any]:
    """Spawn an interactive process and perform scripted expect/send conversation steps.

    command      : The executable or command to spawn.
    interactions : Ordered list of interaction steps. Each step has optional 'expect' (pattern to wait for) and 'send' (text to type after match).
    timeout      : Per-step timeout in seconds. Default 30.
    """
    log = io.StringIO()
    child = _make_child(command, timeout=timeout, log=log)
    transcript: list[str] = []  # toàn bộ output theo từng bước

    try:
        for step_no, step in enumerate(interactions, 1):
            expect_pattern: str | None = step.get("expect")
            send_text: str | None      = step.get("send")

            if expect_pattern:
                # ── Dùng expect() với DANH SÁCH pattern ─────────────────
                # expect() trả về index của pattern đầu tiên khớp.
                # Luôn thêm EOF và TIMEOUT vào cuối để bắt mọi tình huống.
                idx = child.expect([expect_pattern, EOF, TIMEOUT])

                before = _strip_ansi(child.before or "")
                after  = _strip_ansi(child.after  or "")  # phần đã khớp

                if idx == 0:
                    # Khớp đúng pattern mong đợi
                    transcript.append(f"[step {step_no}] matched={repr(after)}  before={repr(before)}")
                elif idx == 1:
                    # Process kết thúc bất ngờ trước khi pattern xuất hiện
                    transcript.append(f"[step {step_no}] EOF before '{expect_pattern}': {before}")
                    break
                elif idx == 2:
                    # Timeout
                    return {
                        "success": False,
                        "command": command,
                        "error": f"Step {step_no}: timeout waiting for '{expect_pattern}'.",
                        "partial_output": "\n".join(transcript),
                    }

            if send_text is not None:
                # ── sendline() gửi text + newline (\\n) ─────────────────
                child.sendline(send_text)
                transcript.append(f"[step {step_no}] sent={repr(send_text)}")

        # ── Đọc hết output còn lại sau tất cả các bước ──────────────────
        try:
            child.expect(EOF, timeout=10)
            tail = _strip_ansi(child.before or "").strip()
            if tail:
                transcript.append(f"[tail] {tail}")
        except (TIMEOUT, EOF):
            pass

    except Exception as exc:
        return {"success": False, "command": command, "error": str(exc)}

    # Log đầy đủ (tất cả I/O đã ghi vào StringIO)
    full_log = _strip_ansi(log.getvalue()).strip()

    return {
        "success": True,
        "command": command,
        "transcript": transcript,       # chuỗi bước expect/send có chú thích
        "full_log": full_log,           # toàn bộ raw I/O qua logfile
    }


# Tool definitions & dispatcher → xem ai_skills.tools
