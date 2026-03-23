from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from terminana.config.settings import (
    OPENAI_OAUTH_JWT_AUTH_CLAIM,
    OPENAI_OAUTH_STATE_DIR,
    OPENAI_OAUTH_STATE_FILE,
)


JWT_AUTH_CLAIM = OPENAI_OAUTH_JWT_AUTH_CLAIM
STATE_DIR = OPENAI_OAUTH_STATE_DIR
AUTH_FILE = OPENAI_OAUTH_STATE_FILE


@dataclass
class OpenAIOAuthState:
    id_token: str
    session_access_token: str
    refresh_token: str
    api_key: str
    account_id: str | None = None
    email: str | None = None
    expires_at: float | None = None
    api_key_obtained_at: float | None = None


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_account_info(id_token: str, access_token: str | None = None) -> tuple[str | None, str | None]:
    id_payload = _decode_jwt_payload(id_token)
    auth_claims = id_payload.get(JWT_AUTH_CLAIM, {})
    if not isinstance(auth_claims, dict):
        auth_claims = {}

    account_id = auth_claims.get("chatgpt_account_id")
    email = id_payload.get("email")

    if isinstance(account_id, str) and account_id.strip():
        return account_id, email if isinstance(email, str) else None

    if access_token:
        access_payload = _decode_jwt_payload(access_token)
        auth_claims = access_payload.get(JWT_AUTH_CLAIM, {})
        if isinstance(auth_claims, dict):
            account_id = auth_claims.get("chatgpt_account_id")
            if isinstance(account_id, str) and account_id.strip():
                return account_id, email if isinstance(email, str) else None

    return None, email if isinstance(email, str) else None


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_openai_oauth_state() -> OpenAIOAuthState | None:
    if not AUTH_FILE.exists():
        return None
    data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    return OpenAIOAuthState(**data)


def save_openai_oauth_state(state: OpenAIOAuthState) -> None:
    _ensure_state_dir()
    AUTH_FILE.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def has_stored_openai_oauth() -> bool:
    try:
        state = load_openai_oauth_state()
    except Exception:
        return False
    return bool(state and state.refresh_token)


def build_state_from_tokens(tokens: dict[str, Any]) -> OpenAIOAuthState:
    id_token = str(tokens.get("id_token", "")).strip()
    access_token = str(tokens.get("access_token", "")).strip()
    refresh_token = str(tokens.get("refresh_token", "")).strip()
    if not id_token or not access_token or not refresh_token:
        raise RuntimeError("Phản hồi token OAuth của OpenAI thiếu dữ liệu bắt buộc.")

    account_id, email = _extract_account_info(id_token, access_token)
    expires_in = tokens.get("expires_in")
    expires_at = time.time() + float(expires_in) if isinstance(expires_in, (int, float)) else None
    return OpenAIOAuthState(
        id_token=id_token,
        session_access_token=access_token,
        refresh_token=refresh_token,
        api_key="",
        account_id=account_id,
        email=email,
        expires_at=expires_at,
        api_key_obtained_at=time.time(),
    )
