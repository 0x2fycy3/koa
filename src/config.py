import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
COMMAND_PREFIX = os.environ.get("COMMAND_PREFIX", "!")
COOLDOWN_SECONDS = float(os.environ.get("COOLDOWN_SECONDS", "3.0"))

_raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {int(uid.strip()) for uid in _raw_ids.split(",") if uid.strip()}

_raw_guild_id = os.environ.get("GUILD_ID", "")
GUILD_ID: int | None = int(_raw_guild_id) if _raw_guild_id.strip() else None
