"""
ai_skills/chat/telegram.py
──────────────────────────
Telegram bot runner cho Terminana.

Public API
──────────
get_token() -> str
run(token, provider, api_key, model)
"""
from __future__ import annotations

import asyncio
import getpass
import os
from pathlib import Path

from rich.console import Console

from terminana.chat.session import new_session

console  = Console()
_ENV     = Path(__file__).resolve().parent.parent.parent / ".env"


def get_token() -> str:
    """Lấy Telegram Bot Token từ env hoặc prompt người dùng."""
    from dotenv import load_dotenv
    load_dotenv(_ENV)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("  Nhập Telegram Bot Token: ").strip()
        if not token:
            raise ValueError("Token trống.")
        if input("  Lưu vào .env? [y/N] ").strip().lower() == "y":
            with open(_ENV, "a", encoding="utf-8") as f:
                f.write(f"\nTELEGRAM_BOT_TOKEN={token}\n")
            console.print("  [dim]Đã lưu.[/]")
    return token


def run(token: str, provider: str, api_key: str, model: str, enabled_tools: list[str] | None = None) -> None:
    """Khởi chạy Telegram bot, block cho đến khi Ctrl+C."""
    from telegram import Update
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )

    _sessions: dict[int, any] = {}

    def _get_ask(uid: int):
        if uid not in _sessions:
            _sessions[uid] = new_session(provider, api_key, model, enabled_tools=enabled_tools)
        return _sessions[uid]

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        uid = update.effective_user.id
        _sessions.pop(uid, None)
        await update.message.reply_text(
            f"Terminana sẵn sàng.\nProvider: {provider.upper()}  |  Model: {model}\n"
            "/reset để bắt đầu cuộc trò chuyện mới."
        )

    async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        _sessions.pop(update.effective_user.id, None)
        await update.message.reply_text("Session đã được reset.")

    async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        uid      = update.effective_user.id
        text     = update.message.text.strip()
        status   = await update.message.reply_text("Đang xử lý...")

        tool_log: list[str] = []

        def on_tool(info: str) -> None:
            tool_log.append(info)

        ask  = _get_ask(uid)
        loop = asyncio.get_event_loop()
        try:
            reply = await loop.run_in_executor(None, lambda: ask(text))
        except Exception as exc:
            await status.edit_text(f"Lỗi: {exc}")
            return

        prefix = ("\n".join(tool_log) + "\n\n") if tool_log else ""
        await status.edit_text(prefix + reply)
        console.print(f"[dim]tg/{uid}:[/] {text[:60]}")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    console.print("\n[bold green]Telegram bot đang chạy[/]  [dim](Ctrl+C để dừng)[/]")
    app.run_polling(drop_pending_updates=True)
