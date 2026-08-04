import asyncio
from datetime import datetime, timezone

from aiogram import Bot

import database as db

CHECK_INTERVAL_SECONDS = 30
BROADCAST_DELAY = 0.05


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def _run_scheduled_broadcast(bot: Bot, job: dict):
    groups = await db.get_all_groups()
    success, fail = 0, 0
    for g in groups:
        try:
            await bot.copy_message(g["chat_id"], job["source_chat_id"], job["source_message_id"])
            success += 1
        except Exception:
            fail += 1
            await db.remove_group(g["chat_id"])
        await asyncio.sleep(BROADCAST_DELAY)

    await db.mark_broadcast_done(job["id"])
    await db.log_broadcast(len(groups), success, fail, False)
    await db.log_owner_action(job["created_by"], "scheduled_broadcast", f"{success}/{len(groups)} sent")


async def _apply_due_template_schedules(bot: Bot, now: str):
    starts = await db.get_due_template_starts(now)
    for s in starts:
        ok = await db.load_template(s["chat_id"], s["template_name"])
        if ok:
            await db.mark_schedule_applied(s["id"])

    ends = await db.get_due_template_ends(now)
    for e in ends:
        await db.reset_welcome(e["chat_id"])
        await db.mark_schedule_reverted(e["id"])


async def scheduler_loop(bot: Bot):
    """
    Background loop — har CHECK_INTERVAL_SECONDS mein due scheduled broadcasts
    aur template schedules check karke apply karta hai. Bot restart hone par bhi
    DB mein saved jobs safe rehte hai (DB-backed, in-memory nahi).
    """
    while True:
        try:
            now = now_iso()

            due_broadcasts = await db.get_due_broadcasts(now)
            for job in due_broadcasts:
                await _run_scheduled_broadcast(bot, job)

            await _apply_due_template_schedules(bot, now)
        except Exception as e:
            print(f"Scheduler loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
