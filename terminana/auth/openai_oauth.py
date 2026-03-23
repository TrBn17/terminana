from __future__ import annotations

import time

from terminana.auth.openai_oauth_login import login_openai_chatgpt, refresh_openai_oauth_tokens
from terminana.auth.openai_oauth_store import (
    OpenAIOAuthState,
    build_state_from_tokens,
    has_stored_openai_oauth,
    load_openai_oauth_state,
    save_openai_oauth_state,
)
from terminana.config.settings import OPENAI_OAUTH_REFRESH_SKEW_SECONDS


def get_openai_oauth_state(force_refresh: bool = False) -> OpenAIOAuthState:
    state = load_openai_oauth_state()
    if state is None:
        raise RuntimeError("Chưa có thông tin đăng nhập ChatGPT cho OpenAI.")

    should_refresh = force_refresh
    if state.expires_at is not None:
        should_refresh = should_refresh or time.time() >= (state.expires_at - OPENAI_OAUTH_REFRESH_SKEW_SECONDS)

    if should_refresh:
        tokens = refresh_openai_oauth_tokens(state.refresh_token)
        state = build_state_from_tokens(tokens)
        save_openai_oauth_state(state)

    return state


def get_openai_oauth_api_key(force_refresh: bool = False) -> str:
    state = get_openai_oauth_state(force_refresh=force_refresh)
    if not state.api_key:
        raise RuntimeError(
            "Thông tin đăng nhập ChatGPT đã được lưu, nhưng tài khoản này không có OpenAI API key qua OAuth. "
            "Hãy dùng trực tiếp OAuth hoặc nhập API key thủ công nếu cần."
        )
    return state.api_key


__all__ = [
    "OpenAIOAuthState",
    "get_openai_oauth_api_key",
    "get_openai_oauth_state",
    "has_stored_openai_oauth",
    "login_openai_chatgpt",
]
