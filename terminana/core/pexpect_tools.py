"""pexpect-backed tools for command execution and scripted interactions."""

from __future__ import annotations

import io
import re
import sys
from typing import Any

import pexpect
from pexpect import EOF, TIMEOUT

from terminana.tools.decorator import tool

_IS_WIN = sys.platform == "win32"
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]|\x1b\].*?\x07|\x1b[@-Z\\-_]")
_WINDOWS_SHELL_BUILTINS = {
    "cls",
    "copy",
    "del",
    "dir",
    "echo",
    "md",
    "move",
    "popd",
    "pushd",
    "rd",
    "ren",
    "set",
    "type",
}
_TAIL_TIMEOUT_SECONDS = 1

if _IS_WIN:
    from pexpect.popen_spawn import PopenSpawn as _PopenSpawn


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from captured output."""
    return _ANSI_ESCAPE_RE.sub("", text)


def _clean_output(text: str | None) -> str:
    return _strip_ansi(text or "").strip()


def _normalize_command(command: str) -> str:
    """Wrap Windows shell built-ins so PopenSpawn can execute them reliably."""
    if not _IS_WIN:
        return command

    stripped = command.strip()
    if not stripped:
        return command

    first_token = stripped.split(maxsplit=1)[0].lower()
    if first_token in _WINDOWS_SHELL_BUILTINS:
        return f"cmd /c {command}"
    return command


def _make_child(command: str, timeout: int, log: io.StringIO | None = None):
    """Create a platform-appropriate pexpect child process."""
    normalized_command = _normalize_command(command)

    if _IS_WIN:
        child = _PopenSpawn(normalized_command, timeout=timeout, encoding="utf-8")
        if log is not None:
            child.logfile = log
        return child

    child = pexpect.spawn(
        "/bin/bash",
        args=["-c", normalized_command],
        timeout=timeout,
        encoding="utf-8",
    )
    if log is not None:
        child.logfile_read = log
    return child


def _close_child(child: Any) -> None:
    try:
        child.close(force=True)
    except TypeError:
        child.close()
    except Exception:
        pass


def _build_failure(
    command: str,
    error: str,
    *,
    partial_output: str | None = None,
    transcript: list[str] | None = None,
    full_log: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "command": command,
        "error": error,
    }
    if partial_output is not None:
        result["partial_output"] = partial_output
    if transcript is not None:
        result["transcript"] = transcript
    if full_log is not None:
        result["full_log"] = full_log
    return result


@tool
def run_command(command: str, timeout: int = 30) -> dict[str, Any]:
    """Run a shell command and return the captured output."""
    child = None
    try:
        child = _make_child(command, timeout=timeout)
        idx = child.expect([EOF, TIMEOUT])
        output = _clean_output(child.before)

        if idx == 1:
            return _build_failure(
                command,
                f"Command timed out after {timeout}s.",
                partial_output=output,
            )

        return {
            "success": True,
            "command": command,
            "output": output,
        }
    except Exception as exc:
        return _build_failure(command, str(exc))
    finally:
        if child is not None:
            _close_child(child)


@tool
def spawn_and_interact(
    command: str,
    interactions: list[dict[str, str]],
    timeout: int = 30,
) -> dict[str, Any]:
    """Spawn a process and execute ordered expect/send interaction steps."""
    child = None
    log = io.StringIO()
    transcript: list[str] = []

    try:
        child = _make_child(command, timeout=timeout, log=log)

        for step_no, step in enumerate(interactions, start=1):
            if not isinstance(step, dict):
                return _build_failure(
                    command,
                    f"Step {step_no}: interaction must be an object.",
                    transcript=transcript,
                    full_log=_clean_output(log.getvalue()),
                )

            expect_pattern = step.get("expect")
            send_text = step.get("send")

            if expect_pattern is not None and not isinstance(expect_pattern, str):
                return _build_failure(
                    command,
                    f"Step {step_no}: 'expect' must be a string or null.",
                    transcript=transcript,
                    full_log=_clean_output(log.getvalue()),
                )

            if send_text is not None and not isinstance(send_text, str):
                return _build_failure(
                    command,
                    f"Step {step_no}: 'send' must be a string or null.",
                    transcript=transcript,
                    full_log=_clean_output(log.getvalue()),
                )

            if expect_pattern is not None:
                idx = child.expect([expect_pattern, EOF, TIMEOUT])
                before = _clean_output(child.before)

                if idx == 1:
                    transcript.append(
                        f"[step {step_no}] EOF before matching {expect_pattern!r}: {before!r}"
                    )
                    full_log = _clean_output(log.getvalue())
                    return _build_failure(
                        command,
                        f"Step {step_no}: process exited before matching {expect_pattern!r}.",
                        partial_output=full_log or before,
                        transcript=transcript,
                        full_log=full_log,
                    )

                if idx == 2:
                    transcript.append(f"[step {step_no}] timeout waiting for {expect_pattern!r}")
                    full_log = _clean_output(log.getvalue())
                    return _build_failure(
                        command,
                        f"Step {step_no}: timeout waiting for {expect_pattern!r}.",
                        partial_output=full_log or before,
                        transcript=transcript,
                        full_log=full_log,
                    )

                matched = _clean_output(child.after)
                transcript.append(
                    f"[step {step_no}] matched={matched!r} before={before!r}"
                )

            if send_text is not None:
                child.sendline(send_text)
                transcript.append(f"[step {step_no}] sent={send_text!r}")

        idx = child.expect([EOF, TIMEOUT], timeout=_TAIL_TIMEOUT_SECONDS)
        tail = _clean_output(child.before)
        if tail:
            transcript.append(f"[tail] {tail}")
        if idx == 1 and child.isalive():
            transcript.append("[tail] process still running; closing session")

        return {
            "success": True,
            "command": command,
            "transcript": transcript,
            "full_log": _clean_output(log.getvalue()),
        }
    except Exception as exc:
        full_log = _clean_output(log.getvalue())
        return _build_failure(
            command,
            str(exc),
            partial_output=full_log or None,
            transcript=transcript,
            full_log=full_log,
        )
    finally:
        if child is not None:
            _close_child(child)
