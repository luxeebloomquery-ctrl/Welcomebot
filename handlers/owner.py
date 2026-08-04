import asyncio

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import database as db
from config import OWNER_ID
from utils.progress import ProgressMessage
from utils.linkdetect import contains_link
from utils.ownercheck import is_owner

router = Router()

BROADCAST_DELAY = 0.05  # groups ke beech chhota gap, Telegram flood-limit se bachne ke liye


async def _owner_only(message: Message) -> bool:
    return await is_owner(message.from_user.id)


@router.message(Command("owner"))
async def cmd_owner_dashboard(message: Message, bot: Bot):
    if not await _owner_only(message):
        return

    total_groups = await db.get_group_count()
    recent = await db.get_recent_groups(5)
    history = await db.get_broadcast_history(3)

    recent_lines = "\n".join(f"• {g['chat_name'] or g['chat_id']}" for g in recent) or "Koi group nahi"
    history_lines = "\n".join(
        f"• {h['success']}/{h['total']} sent" + (" 🔗" if h["had_link"] else "")
        for h in history
    ) or "Koi broadcast nahi hua abhi tak"

    text = (
        "<b>👑 Owner Dashboard</b>\n\n"
        f"<b>Total Groups:</b> {total_groups}\n\n"
        f"<b>Recently Added:</b>\n{recent_lines}\n\n"
        f"<b>Recent Broadcasts:</b>\n{history_lines}\n\n"
        "Commands: /broadcast /groups /stats /deleteall"
    )
    await message.answer(text)


@router.message(Command("groups"))
async def cmd_groups(message: Message):
    if not await _owner_only(message):
        return

    groups = await db.get_all_groups()
    if not groups:
        await message.answer("Abhi koi group registered nahi hai.")
        return

    lines = [f"{i+1}. {g['chat_name'] or 'Unnamed'} (<code>{g['chat_id']}</code>)" for i, g in enumerate(groups[:50])]
    text = f"<b>📋 Groups ({len(groups)} total)</b>\n\n" + "\n".join(lines)
    if len(groups) > 50:
        text += f"\n\n...aur {len(groups) - 50} groups"
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message, bot: Bot):
    if not await _owner_only(message):
        return

    groups = await db.get_all_groups()
    total_groups = len(groups)

    progress = ProgressMessage(bot, message.chat.id)
    await progress.start("📊 <b>Stats calculate ho rahe hai...</b>", 0)

    total_members = 0
    for idx, g in enumerate(groups):
        count = await db.get_member_count_placeholder(bot, g["chat_id"])
        total_members += count
        percent = round(((idx + 1) / max(total_groups, 1)) * 100)
        await progress.update(percent, f"📊 <b>Stats calculate ho rahe hai...</b> ({idx+1}/{total_groups})")

    recent = await db.get_recent_groups(5)
    recent_lines = "\n".join(f"• {g['chat_name'] or g['chat_id']}" for g in recent) or "Koi nahi"

    final = (
        "✅ <b>Bot Statistics</b>\n\n"
        f"Total Groups: {total_groups}\n"
        f"Total Known Members: {total_members}\n\n"
        f"Recent Groups:\n{recent_lines}"
    )
    await progress.finish(final)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    if not await _owner_only(message):
        return

    source = message.reply_to_message
    if not source:
        await message.answer(
            "Jis message ko broadcast karna hai, usko reply karke <code>/broadcast</code> bhejo.\n"
            "Text, photo, video, GIF, sticker, document — sab support hai."
        )
        return

    groups = await db.get_all_groups()
    total = len(groups)
    if total == 0:
        await message.answer("Abhi koi group registered nahi hai broadcast ke liye.")
        return

    caption_or_text = source.text or source.caption or ""
    has_link = contains_link(caption_or_text)

    progress = ProgressMessage(bot, message.chat.id)
    link_note = "\n🔗 <i>Link detected in message</i>" if has_link else ""
    await progress.start(f"📢 <b>Broadcast shuru...</b> (0/{total}){link_note}", 0)

    success, fail = 0, 0
    for idx, g in enumerate(groups):
        try:
            sent = await source.copy_to(g["chat_id"])
            await db.log_sent_message(g["chat_id"], sent.message_id, kind="broadcast")
            success += 1
        except Exception:
            fail += 1
            # Group ne bot ko remove/block kiya ho sakta hai
            await db.remove_group(g["chat_id"])

        percent = round(((idx + 1) / total) * 100)
        await progress.update(
            percent,
            f"📢 <b>Broadcasting...</b> ({idx+1}/{total}) | ✅ {success} ❌ {fail}{link_note}",
        )
        await asyncio.sleep(BROADCAST_DELAY)

    await db.log_broadcast(total, success, fail, has_link)
    await db.log_owner_action(message.from_user.id, "broadcast", f"{success}/{total} sent")
    await progress.finish(
        f"✅ <b>Broadcast complete!</b>\nSent: {success}/{total}\nFailed: {fail}{link_note}"
    )


@router.message(Command("deleteall"))
async def cmd_deleteall(message: Message, bot: Bot):
    """Current chat mein pichhle 48 ghante ke bot-broadcast messages delete karta hai."""
    if not await _owner_only(message):
        return

    records = await db.get_sent_messages_last_hours(message.chat.id, hours=48)
    if not records:
        await message.answer("Pichhle 48 ghanto mein is chat mein koi bot broadcast message nahi mila.")
        return

    total = len(records)
    progress = ProgressMessage(bot, message.chat.id)
    await progress.start(f"🗑 <b>Deleting messages...</b> (0/{total})", 0)

    deleted, failed = 0, 0
    for idx, rec in enumerate(records):
        try:
            await bot.delete_message(message.chat.id, rec["message_id"])
            deleted += 1
        except Exception:
            failed += 1
        await db.delete_sent_message_record(rec["id"])

        percent = round(((idx + 1) / total) * 100)
        await progress.update(percent, f"🗑 <b>Deleting messages...</b> ({idx+1}/{total})")

    await progress.finish(f"✅ <b>Delete complete!</b>\nDeleted: {deleted}\nFailed: {failed}")
    await db.log_owner_action(message.from_user.id, "deleteall", f"chat {message.chat.id}: {deleted} deleted")
