import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val

TELEGRAM_TOKEN: str = _require("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")

TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")
MORNING_TIME: str = os.getenv("MORNING_TIME", "07:00")
EVENING_TIME: str = os.getenv("EVENING_TIME", "20:00")
REPORT_TIME: str = os.getenv("REPORT_TIME", "18:00")
