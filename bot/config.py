from pathlib import Path
from dotenv import load_dotenv  # pip install python-dotenv
import os

# ищем файл, имя приходит из переменной или берём .env
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(Path(__file__).parent.parent / env_file)

bot_token = os.getenv("BOT_TOKEN")  # ← единственное, что нужно наружу
