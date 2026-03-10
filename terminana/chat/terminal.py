"""
ai_skills/chat/terminal.py
──────────────────────────
Terminal UI: banner 3-D và chat loop.

Public API
──────────
banner()
chat_loop(ask, provider, model, restart, reset)

Các lệnh trong chat loop
─────────────────────────
/help    — hiện danh sách lệnh
/switch  — đổi provider và model (chạy lại setup)
/reset   — bắt đầu cuộc trò chuyện mới, giữ nguyên provider/model
/clear   — xoá màn hình
/quit    — thoát
"""
from __future__ import annotations

import os
from typing import Callable

import pyfiglet
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

console = Console()

# (lệnh, mô tả ngắn)
_COMMANDS: list[tuple[str, str]] = [
    ("/help",   "Hiển thị danh sách lệnh này"),
    ("/switch", "Đổi provider và model (chạy lại setup đầy đủ)"),
    ("/reset",  "Bắt đầu lại cuộc trò chuyện mới, giữ provider/model hiện tại"),
    ("/clear",  "Xoá màn hình terminal"),
    ("/quit",   "Thoát Terminana  (hoặc dùng Ctrl+C)"),
]


def banner() -> None:
    art    = pyfiglet.figlet_format("Terminana", font="larry3d")
    t      = Text()
    colors = [
        "bold bright_white on #005f87",
        "bold bright_cyan",
        "bold cyan",
        "bold #00d7ff",
    ]
    for i, line in enumerate(art.splitlines()):
        t.append(line + "\n", style=colors[i % len(colors)])
    console.print(
        Panel(t, subtitle="[dim]/help để xem lệnh  |  Ctrl+C để thoát[/]",
              border_style="bright_cyan", expand=False)
    )


def _print_help(provider: str, model: str) -> None:
    tbl = Table(
        title="Các lệnh có sẵn",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )
    tbl.add_column("Lệnh",      style="bold white",  no_wrap=True, min_width=10)
    tbl.add_column("Mô tả",     style="dim",         no_wrap=False)
    for cmd, desc in _COMMANDS:
        tbl.add_row(cmd, desc)
    console.print()
    console.print(tbl)
    console.print(
        f"  Đang dùng: [bold]{provider.upper()}[/] / [bold]{model}[/]\n"
    )


def chat_loop(
    ask: Callable[[str], str],
    *,
    provider: str = "",
    model: str = "",
    restart: Callable[[], tuple[Callable[[str], str], str, str]] | None = None,
    reset: Callable[[], Callable[[str], str]] | None = None,
) -> None:
    """
    Vòng lặp chat chính.

    Parameters
    ----------
    ask      : hàm nhận prompt -> trả lời
    provider : tên provider hiện tại (chỉ hiển thị)
    model    : tên model hiện tại (chỉ hiển thị)
    restart  : callable() -> (new_ask, new_provider, new_model)
               Dùng cho /switch — chạy lại setup đầy đủ.
    reset    : callable() -> new_ask
               Dùng cho /reset — tạo session mới, giữ provider/model.
    """
    while True:
        try:
            prompt_label = f"[{provider}/{model}]" if provider and model else ""
            user = input(f"you{prompt_label}> ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user:
            continue

        cmd = user.lower()

        if cmd in ("/quit", "/exit", "quit", "exit"):
            break

        if cmd == "/help":
            _print_help(provider, model)
            continue

        if cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            banner()
            continue

        if cmd == "/switch":
            if restart is None:
                console.print("  [red]Không hỗ trợ switch trong chế độ này.[/]")
                continue
            console.print()
            ask, provider, model = restart()
            console.print(f"\n  [dim]> Đã chuyển sang {provider.upper()} / {model}[/]\n")
            continue

        if cmd == "/reset":
            if reset is None:
                console.print("  [red]Không hỗ trợ reset trong chế độ này.[/]")
                continue
            ask = reset()
            console.print(f"  [dim]> Session mới: {provider.upper()} / {model}[/]\n")
            continue

        if cmd.startswith("/"):
            console.print(
                f"  [red]Lệnh không tồn tại:[/] {cmd}  "
                f"([dim]/help để xem danh sách[/])"
            )
            continue

        with Live(Spinner("dots", text="[cyan]thinking...[/]"),
                  console=console, transient=True):
            reply = ask(user)

        console.print(
            Panel(Markdown(reply),
                  title=f"[bold green]Terminana[/] [dim]{provider}/{model}[/]",
                  border_style="green")
        )

    console.print("[dim]Tạm biệt.[/]")
