import os
import resource
import sys

import aiogram
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import database as db
from config import DB_PATH
from utils.ownercheck import is_owner
from utils.health import get_uptime_seconds, format_uptime

router = Router()


@router.message(Command("health"))
async def cmd_health(message: Message):
    if not await is_owner(message.from_user.id):
        return

    uptime = format_uptime(get_uptime_seconds())

    ram_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # Linux: KB
    ram_mb = ram_kb / 1024

    db_size_mb = 0.0
    if os.path.exists(DB_PATH):
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)

    total_groups = await db.get_group_count()
    pending_broadcasts = len(await db.list_pending_broadcasts())

    text = (
        "<b>🩺 Bot Health Dashboard</b>\n\n"
        f"Uptime: {uptime}\n"
        f"Python: {sys.version.split()[0]}\n"
        f"aiogram: {aiogram.__version__}\n"
        f"Memory usage: {ram_mb:.1f} MB\n"
        f"Database size: {db_size_mb:.2f} MB\n\n"
        f"Total Groups: {total_groups}\n"
        f"Pending Scheduled Broadcasts: {pending_broadcasts}\n"
    )
    await message.answer(text)
