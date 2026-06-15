from pathlib import Path
from dotenv import load_dotenv  # pip install python-dotenv
import os

# ищем файл, имя приходит из переменной или берём .env
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(Path(__file__).parent.parent / env_file)

bot_token = os.getenv("BOT_TOKEN")  # ← единственное, что нужно наружу
feedback_channel_id = os.getenv("FEEDBACK_CHANNEL_ID")


def get_feedback_chat_id(value: str | None = None) -> int | str:
    """Return a Telegram chat ID as an integer or @username."""
    normalized = (feedback_channel_id if value is None else value) or ""
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("FEEDBACK_CHANNEL_ID is not configured")
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    if normalized.startswith("@") and len(normalized) > 1:
        return normalized
    raise ValueError("FEEDBACK_CHANNEL_ID must be a numeric ID or @channel_username")
