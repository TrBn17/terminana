"""
ai_skills/cli.py
────────────────
Console-script entry point.  Registered via pyproject.toml as:

    terminana = "ai_skills.cli:cli"

After  `pip install -e .`  (or  `pip install terminana`  from PyPI):

    terminana start            # khoi dong terminal chat
    terminana telegram         # chay Telegram bot
    terminana --help           # xem huong dan

"""
from __future__ import annotations

import argparse
import sys

# ── Sub-commands ──────────────────────────────────────────────────────────

def _cmd_start(_args: argparse.Namespace) -> None:
    """Khoi dong terminal chat Terminana."""
    from terminana.chat.setup    import setup
    from terminana.chat.session  import new_session
    from terminana.chat.terminal import banner, chat_loop
    from rich.console import Console

    console = Console()
    banner()

    provider, model, api_key, enabled_tools = setup()
    console.print(f"  [dim]> {provider.upper()} / {model}  —  tools: {enabled_tools}[/]\n")

    def restart():
        nonlocal provider, model, api_key, enabled_tools
        provider, model, api_key, enabled_tools = setup()
        return new_session(provider, api_key, model, enabled_tools=enabled_tools), provider, model

    def reset():
        return new_session(provider, api_key, model, enabled_tools=enabled_tools)

    chat_loop(
        new_session(provider, api_key, model, enabled_tools=enabled_tools),
        provider=provider,
        model=model,
        restart=restart,
        reset=reset,
    )


def _cmd_telegram(_args: argparse.Namespace) -> None:
    """Chay Telegram bot Terminana."""
    from terminana.chat.setup    import setup
    from terminana.chat.session  import new_session  # noqa: F401 (kept for clarity)
    from terminana.chat.telegram import get_token, run
    from terminana.chat.terminal import banner
    from rich.console import Console

    console = Console()
    banner()

    provider, model, api_key, enabled_tools = setup()
    console.print(f"  [dim]> {provider.upper()} / {model}  —  tools: {enabled_tools}[/]")

    run(get_token(), provider, api_key, model, enabled_tools=enabled_tools)


# ── Parser ────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terminana",
        description="Terminana — terminal & Telegram AI chat (Gemini / OpenAI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  start       Khởi động terminal chat (mặc định nếu không truyền gì)
  telegram    Chạy Telegram bot

examples:
  terminana start
  terminana telegram
  terminana --help
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    sub.add_parser("start",    help="Khởi động terminal chat")
    sub.add_parser("telegram", help="Chạy Telegram bot")
    sub.add_parser("help",     help="Hiển thị trợ giúp này")

    return parser


# ── Entry ─────────────────────────────────────────────────────────────────

def cli(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args   = parser.parse_args(argv)

    if args.command in ("start", None):
        _cmd_start(args)
    elif args.command == "telegram":
        _cmd_telegram(args)
    elif args.command == "help":
        parser.print_help()
    else:
        parser.print_help()
        sys.exit(1)


# Cho phép chạy trực tiếp: python -m ai_skills.cli start
if __name__ == "__main__":
    cli()
