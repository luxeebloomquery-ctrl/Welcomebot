from datetime import datetime, timezone

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from utils.ownercheck import is_owner
from utils.scheduler import now_iso

router = Router()

DATE_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%d"]


def _parse_datetime(raw: str) -> str | None:
    """User input (UTC maana jaata hai) ko DB-comparable ISO string mein convert karta hai."""
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


@router.message(Command("schedulebroadcast"))
async def cmd_schedulebroadcast(message: Message, command: CommandObject, bot: Bot):
    if not await is_owner(message.from_user.id):
        return

    if not message.reply_to_message:
        await message.answer(
            "Jis message ko schedule karna hai usko reply karke bhejo:\n"
            "<code>/schedulebroadcast 2026-08-15 09:00</code> (UTC time, 24-hour format)"
        )
        return

    run_at = _parse_datetime(command.args or "")
    if not run_at:
        await message.answer(
            "Time format galat hai. Use: <code>/schedulebroadcast 2026-08-15 09:00</code> (UTC, YYYY-MM-DD HH:MM)"
        )
        return

    if run_at <= now_iso():
        await message.answer("⚠️ Ye time already beet chuka hai. Future ka time do.")
        return

    await db.add_scheduled_broadcast(
        message.chat.id, message.reply_to_message.message_id, run_at, message.from_user.id
    )
    await message.answer(f"⏰ Broadcast schedule ho gaya — <b>{run_at} UTC</b> pe sab groups mein bhejega.")


@router.message(Command("pendingbroadcasts"))
async def cmd_pendingbroadcasts(message: Message):
    if not await is_owner(message.from_user.id):
        return

    jobs = await db.list_pending_broadcasts()
    if not jobs:
        await message.answer("Koi scheduled broadcast pending nahi hai.")
        return

    lines = "\n".join(f"• ID {j['id']} — {j['run_at']} UTC" for j in jobs)
    await message.answer(f"<b>⏰ Pending Broadcasts</b>\n\n{lines}\n\nCancel: <code>/cancelbroadcast ID</code>")


@router.message(Command("cancelbroadcast"))
async def cmd_cancelbroadcast(message: Message, command: CommandObject):
    if not await is_owner(message.from_user.id):
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("ID do: <code>/cancelbroadcast 3</code> (list ke liye /pendingbroadcasts)")
        return

    ok = await db.cancel_scheduled_broadcast(int(arg))
    if ok:
        await message.answer(f"✅ Broadcast ID {arg} cancel kar diya gaya.")
    else:
        await message.answer("❌ Ye ID pending list mein nahi mili.")


# ---------- Scheduled Welcome Templates ----------

@router.message(Command("scheduletemplate"))
async def cmd_scheduletemplate(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return

    from utils.admin import is_admin
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    parts = (command.args or "").split()
    if len(parts) != 3:
        await message.answer(
            "Use: <code>/scheduletemplate diwali 2026-10-20 2026-10-25</code>\n"
            "(template naam, start date, end date — UTC, YYYY-MM-DD)"
        )
        return

    name, start_raw, end_raw = parts
    start_at = _parse_datetime(start_raw)
    end_at = _parse_datetime(end_raw)
    if not start_at or not end_at:
        await message.answer("Date format galat hai. YYYY-MM-DD use karo.")
        return

    tpl = await db.get_template(message.chat.id, name)
    if tpl is None:
        await message.answer(f"❌ '{name}' naam ka template nahi mila. Pehle /savetemplate karo.")
        return

    await db.add_template_schedule(message.chat.id, name, start_at, end_at)
    await message.answer(
        f"📅 Template '<b>{name}</b>' <b>{start_at}</b> se <b>{end_at}</b> tak (UTC) automatically active rahega."
    )


@router.message(Command("templateschedules"))
async def cmd_templateschedules(message: Message):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return

    schedules = await db.list_template_schedules(message.chat.id)
    if not schedules:
        await message.answer("Koi scheduled template nahi hai.")
        return

    lines = []
    for s in schedules:
        status = "✅ active" if s["applied"] else "⏳ upcoming"
        lines.append(f"• {s['template_name']}: {s['start_at']} → {s['end_at']} ({status})")
    await message.answer("<b>📅 Template Schedules</b>\n\n" + "\n".join(lines))
