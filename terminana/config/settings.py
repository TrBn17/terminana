"""
Project configuration - loads environment variables from .env
"""
import os
import getpass
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH     = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# --- Providers & models ---
PROVIDERS: dict = {
    "gemini": {"env_key": "GEMINI_API_KEY"},
    "openai": {"env_key": "OPENAI_API_KEY"},
}


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        if min_value is not None and value < min_value:
            return default
        return value
    except ValueError:
        return default


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default[:]
    values = [item.strip() for item in raw.split(",")]
    values = [item for item in values if item]
    return values or default[:]


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    return Path(raw).expanduser() if raw else default

def get_api_key(provider: str) -> str:
    """Lấy API key: từ env → nếu thiếu thì prompt, hỏi có lưu .env không."""
    cfg = PROVIDERS[provider]
    key = os.getenv(cfg["env_key"], "")
    if not key:
        key = getpass.getpass(f"  Nhập {cfg['env_key']}: ").strip()
        if not key:
            raise EnvironmentError(f"{cfg['env_key']} trống.")
        if input("  Lưu vào .env để dùng lại? [y/N] ").strip().lower() == "y":
            with open(_ENV_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n{cfg['env_key']}={key}\n")
            print(f"  ✓ Đã lưu vào {_ENV_PATH}")
    return key


# --- OpenAI OAuth config ---
OPENAI_OAUTH_ISSUER: str = os.getenv("OPENAI_OAUTH_ISSUER", "https://auth.openai.com").rstrip("/")
OPENAI_OAUTH_AUTHORIZE_URL: str = os.getenv(
    "OPENAI_OAUTH_AUTHORIZE_URL", f"{OPENAI_OAUTH_ISSUER}/oauth/authorize"
)
OPENAI_OAUTH_TOKEN_URL: str = os.getenv(
    "OPENAI_OAUTH_TOKEN_URL", f"{OPENAI_OAUTH_ISSUER}/oauth/token"
)
OPENAI_OAUTH_CLIENT_ID: str = os.getenv("OPENAI_OAUTH_CLIENT_ID", "app_EMoamEEZ73f0CkXaXp7hrann")
OPENAI_OAUTH_BIND_HOST: str = os.getenv("OPENAI_OAUTH_BIND_HOST", "127.0.0.1")
OPENAI_OAUTH_REDIRECT_PORT: int = _env_int("OPENAI_OAUTH_REDIRECT_PORT", 1455, min_value=1)
OPENAI_OAUTH_REDIRECT_PATH: str = os.getenv("OPENAI_OAUTH_REDIRECT_PATH", "/auth/callback")
OPENAI_OAUTH_REDIRECT_HOST: str = os.getenv("OPENAI_OAUTH_REDIRECT_HOST", "localhost")
OPENAI_OAUTH_REDIRECT_URI: str = os.getenv(
    "OPENAI_OAUTH_REDIRECT_URI",
    f"http://{OPENAI_OAUTH_REDIRECT_HOST}:{OPENAI_OAUTH_REDIRECT_PORT}{OPENAI_OAUTH_REDIRECT_PATH}",
)
OPENAI_OAUTH_SCOPE: str = os.getenv(
    "OPENAI_OAUTH_SCOPE",
    "openid profile email offline_access api.connectors.read api.connectors.invoke",
)
OPENAI_OAUTH_REQUEST_TIMEOUT: int = _env_int("OPENAI_OAUTH_REQUEST_TIMEOUT", 60, min_value=1)
OPENAI_OAUTH_BROWSER_WAIT_TIMEOUT: int = _env_int("OPENAI_OAUTH_BROWSER_WAIT_TIMEOUT", 120, min_value=1)
OPENAI_OAUTH_REFRESH_SKEW_SECONDS: int = _env_int("OPENAI_OAUTH_REFRESH_SKEW_SECONDS", 60, min_value=0)
OPENAI_OAUTH_BASE_URL: str = os.getenv(
    "OPENAI_OAUTH_BASE_URL", "https://chatgpt.com/backend-api/codex"
)
OPENAI_OAUTH_MODELS: list[str] = _env_csv(
    "OPENAI_OAUTH_MODELS",
    ["gpt-5.4", "gpt-5.3-codex", "codex-mini-latest"],
)
OPENAI_OAUTH_JWT_AUTH_CLAIM: str = os.getenv("OPENAI_OAUTH_JWT_AUTH_CLAIM", "https://api.openai.com/auth")
OPENAI_OAUTH_STATE_DIR: Path = _env_path("OPENAI_OAUTH_STATE_DIR", Path.home() / ".terminana")
OPENAI_OAUTH_STATE_FILE: Path = _env_path("OPENAI_OAUTH_STATE_FILE", OPENAI_OAUTH_STATE_DIR / "auth.json")

# --- Defaults (backward compat) ---
DEFAULT_TIMEOUT: int = 30
GEMINI_MODEL:    str  = "gemini-2.5-flash"
GEMINI_API_KEY:  str  = os.getenv("GEMINI_API_KEY", "")
