import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable set nahi hai! .env file check karo.")

if not OWNER_ID:
    raise RuntimeError("OWNER_ID environment variable set nahi hai! .env file check karo.")

DB_PATH = os.getenv("DB_PATH", "welcome_bot.db")
