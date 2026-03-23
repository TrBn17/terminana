from __future__ import annotations

import hashlib
import json
import secrets
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, cast

from terminana.config.settings import (
    OPENAI_OAUTH_AUTHORIZE_URL,
    OPENAI_OAUTH_BIND_HOST,
    OPENAI_OAUTH_BROWSER_WAIT_TIMEOUT,
    OPENAI_OAUTH_CLIENT_ID,
    OPENAI_OAUTH_REDIRECT_PATH,
    OPENAI_OAUTH_REDIRECT_PORT,
    OPENAI_OAUTH_REDIRECT_URI,
    OPENAI_OAUTH_REQUEST_TIMEOUT,
    OPENAI_OAUTH_SCOPE,
    OPENAI_OAUTH_TOKEN_URL,
)
from terminana.auth.openai_oauth_store import build_state_from_tokens, save_openai_oauth_state


AUTHORIZE_URL = OPENAI_OAUTH_AUTHORIZE_URL
TOKEN_URL = OPENAI_OAUTH_TOKEN_URL
CLIENT_ID = OPENAI_OAUTH_CLIENT_ID
BIND_HOST = OPENAI_OAUTH_BIND_HOST
REDIRECT_PORT = OPENAI_OAUTH_REDIRECT_PORT
REDIRECT_PATH = OPENAI_OAUTH_REDIRECT_PATH
REDIRECT_URI = OPENAI_OAUTH_REDIRECT_URI
OAUTH_SCOPE = OPENAI_OAUTH_SCOPE


def _urlsafe_b64(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _generate_pkce() -> tuple[str, str]:
    verifier = _urlsafe_b64(secrets.token_bytes(32))
    challenge = _urlsafe_b64(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _post_form(url: str, payload: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=OPENAI_OAUTH_REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Yêu cầu OAuth tới OpenAI thất bại ({exc.code}): {detail}") from exc


def exchange_code_for_tokens(code: str, verifier: str) -> dict[str, Any]:
    return _post_form(
        TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
        },
    )


def refresh_openai_oauth_tokens(refresh_token: str) -> dict[str, Any]:
    return _post_form(
        TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
        },
    )


class _OAuthCallbackServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], request_handler_class: type[BaseHTTPRequestHandler], expected_state: str):
        super().__init__(server_address, request_handler_class)
        self.expected_state = expected_state
        self.authorization_code: str | None = None
        self.error_message: str | None = None
        self.done = threading.Event()


class _OAuthCallbackServerV6(HTTPServer):
    address_family = socket.AF_INET6
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], request_handler_class: type[BaseHTTPRequestHandler], expected_state: str):
        super().__init__(server_address, request_handler_class)
        self.expected_state = expected_state
        self.authorization_code: str | None = None
        self.error_message: str | None = None
        self.done = threading.Event()


class _OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        server = cast(_OAuthCallbackServer, self.server)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write("Không tìm thấy".encode("utf-8"))
            return

        params = urllib.parse.parse_qs(parsed.query)
        state = (params.get("state") or [""])[0]
        if state != server.expected_state:
            server.error_message = "Giá trị state không khớp trong phản hồi OAuth của OpenAI."
            self.send_response(400)
            self.end_headers()
            self.wfile.write("State không khớp".encode("utf-8"))
            server.done.set()
            return

        error = (params.get("error") or [""])[0]
        if error:
            description = (params.get("error_description") or [error])[0]
            server.error_message = f"Đăng nhập OAuth với OpenAI thất bại: {description}"
            self.send_response(400)
            self.end_headers()
            self.wfile.write(description.encode("utf-8", errors="replace"))
            server.done.set()
            return

        code = (params.get("code") or [""])[0]
        if not code:
            server.error_message = "Phản hồi OAuth của OpenAI không chứa mã xác thực."
            self.send_response(400)
            self.end_headers()
            self.wfile.write("Thiếu mã xác thực".encode("utf-8"))
            server.done.set()
            return

        server.authorization_code = code
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<!doctype html><html><body><p>Đăng nhập thành công. Hãy quay lại cửa sổ terminal để tiếp tục.</p></body></html>".encode("utf-8")
        )
        print("  Đã nhận phản hồi OAuth từ trình duyệt. Đang hoàn tất đăng nhập...", flush=True)
        server.done.set()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def _parse_manual_callback(value: str) -> tuple[str | None, str | None, str | None]:
    raw = value.strip()
    if not raw:
        return None, None, None
    if "://" in raw:
        try:
            parsed = urllib.parse.urlparse(raw)
            params = urllib.parse.parse_qs(parsed.query)
            return (params.get("code") or [None])[0], (params.get("state") or [None])[0], raw
        except Exception:
            pass

    params = urllib.parse.parse_qs(raw)
    if "code" in params:
        return (params.get("code") or [None])[0], (params.get("state") or [None])[0], raw
    return raw, None, raw


def login_openai_chatgpt() -> str:
    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "terminana",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    server: _OAuthCallbackServer | _OAuthCallbackServerV6 | None = None
    try:
        server = _OAuthCallbackServer((BIND_HOST, REDIRECT_PORT), _OAuthHandler, state)
    except OSError:
        try:
            server = _OAuthCallbackServerV6(("::1", REDIRECT_PORT), _OAuthHandler, state)
        except OSError:
            pass

    if server is not None:
        threading.Thread(target=server.serve_forever, daemon=True).start()

    print("  Đang mở trình duyệt để đăng nhập ChatGPT...", flush=True)
    opened = webbrowser.open(auth_url)
    if not opened:
        print("  Không thể mở trình duyệt tự động. Hãy mở liên kết bên dưới theo cách thủ công:", flush=True)
        print(f"\n{auth_url}\n")

    if server is not None:
        print(f"  Đang chờ phản hồi đăng nhập tại {REDIRECT_URI}...", flush=True)
        server.done.wait(timeout=OPENAI_OAUTH_BROWSER_WAIT_TIMEOUT)
    try:
        if server is not None and server.error_message:
            raise RuntimeError(server.error_message)
        code = server.authorization_code if server is not None else None
        if not code:
            print("  Chưa nhận được phản hồi từ trình duyệt.", flush=True)
            print("  Hãy dán URL phản hồi hoặc mã xác thực vào đây:", flush=True)
            print(f"\n{auth_url}\n")
            manual = input("  URL hoặc mã: ").strip()
            code, callback_state, _ = _parse_manual_callback(manual)
            if callback_state and callback_state != state:
                raise RuntimeError("Giá trị state không khớp trong URL phản hồi đã dán.")
            if not code:
                raise RuntimeError("Không tìm thấy mã xác thực để hoàn tất đăng nhập OAuth với OpenAI.")

        print("  Đang đổi mã xác thực để lấy token OAuth...", flush=True)
        tokens = exchange_code_for_tokens(code, verifier)
        oauth_state = build_state_from_tokens(tokens)
        save_openai_oauth_state(oauth_state)
        print("  Đã lưu thông tin đăng nhập ChatGPT cho OpenAI.", flush=True)
        return oauth_state.session_access_token
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
