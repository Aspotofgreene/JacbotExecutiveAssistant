import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _require_int(key: str) -> int:
    val = _require(key)
    try:
        return int(val)
    except ValueError as e:
        raise RuntimeError(f"{key} must be an integer, got {val!r}") from e


def _int_env(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USER_ID: int = _require_int("TELEGRAM_ALLOWED_USER_ID")

# Ollama — Mac mini (light tasks: task evaluation, categorization)
OLLAMA_MAC_URL: str = os.getenv("OLLAMA_MAC_URL", "http://localhost:11434")
OLLAMA_MAC_MODEL: str = os.getenv("OLLAMA_MAC_MODEL", "qwen3:14b")

# Ollama — Desktop GPU (heavy tasks: weekly/monthly/yearly reports)
OLLAMA_DESKTOP_URL: str = os.getenv("OLLAMA_DESKTOP_URL", OLLAMA_MAC_URL)
OLLAMA_DESKTOP_MODEL: str = os.getenv("OLLAMA_DESKTOP_MODEL", OLLAMA_MAC_MODEL)

# Scheduler
TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")
DAILY_TASK_HOUR: int = _int_env("DAILY_TASK_HOUR", 7)
DAILY_TASK_MINUTE: int = _int_env("DAILY_TASK_MINUTE", 0)
EVENING_TIME: str = os.getenv("EVENING_TIME", "20:00")
REPORT_TIME: str = os.getenv("REPORT_TIME", "18:00")
