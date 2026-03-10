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

# --- Defaults (backward compat) ---
DEFAULT_TIMEOUT: int = 30
GEMINI_MODEL:    str  = "gemini-2.5-flash"
GEMINI_API_KEY:  str  = os.getenv("GEMINI_API_KEY", "")
