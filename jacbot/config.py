import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val

TELEGRAM_TOKEN: str = _require("TELEGRAM_TOKEN")

# Ollama — Mac mini (light tasks: task evaluation, categorization)
OLLAMA_MAC_URL: str = os.getenv("OLLAMA_MAC_URL", "http://localhost:11434")
OLLAMA_MAC_MODEL: str = os.getenv("OLLAMA_MAC_MODEL", "qwen3:14b")

# Ollama — Desktop GPU (heavy tasks: weekly/monthly/yearly reports)
OLLAMA_DESKTOP_URL: str = os.getenv("OLLAMA_DESKTOP_URL", OLLAMA_MAC_URL)
OLLAMA_DESKTOP_MODEL: str = os.getenv("OLLAMA_DESKTOP_MODEL", OLLAMA_MAC_MODEL)

TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")
MORNING_TIME: str = os.getenv("MORNING_TIME", "07:00")
EVENING_TIME: str = os.getenv("EVENING_TIME", "20:00")
REPORT_TIME: str = os.getenv("REPORT_TIME", "18:00")
