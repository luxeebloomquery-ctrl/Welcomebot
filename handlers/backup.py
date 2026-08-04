import json

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BufferedInputFile

import database as db
from utils.admin import is_admin
from utils.ownercheck import is_owner

router = Router()


async def _read_uploaded_json(message: Message, bot: Bot) -> dict | None:
    reply = message.reply_to_message
    if not reply or not reply.document:
        return None
    try:
        buf = await bot.download(reply.document.file_id)
        raw = buf.read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


# ---------- Per-group Backup / Restore ----------

@router.message(Command("backup"))
async def cmd_backup(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    config = await db.export_chat_config(message.chat.id)
    raw = json.dumps(config, indent=2, ensure_ascii=False).encode("utf-8")
    file = BufferedInputFile(raw, filename=f"welcome_backup_{message.chat.id}.json")
    await bot.send_document(message.chat.id, file, caption="✅ Is group ka welcome config backup.")


@router.message(Command("restore"))
async def cmd_restore(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    data = await _read_uploaded_json(message, bot)
    if data is None:
        await message.answer(
            "Backup JSON file pe reply karke <code>/restore</code> bhejo.\n"
            "(<code>/backup</code> se banayi gayi file hi use karo)"
        )
        return

    try:
        await db.ensure_chat_row(message.chat.id, message.chat.title or "")
        await db.import_chat_config(message.chat.id, data)
        await message.answer("✅ Backup restore ho gaya! /preview se check karo.")
    except Exception as e:
        await message.answer(f"❌ Restore fail hua: file format sahi nahi hai.\n{e}")


# ---------- Owner-level full Import/Export ----------

@router.message(Command("export"))
async def cmd_export(message: Message, bot: Bot):
    if not await is_owner(message.from_user.id):
        return

    data = await db.export_all_config()
    raw = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    file = BufferedInputFile(raw, filename="full_bot_export.json")
    await bot.send_document(
        message.chat.id, file, caption=f"✅ Full export: {len(data['groups'])} groups."
    )
    await db.log_owner_action(message.from_user.id, "export", f"{len(data['groups'])} groups")


@router.message(Command("import"))
async def cmd_import(message: Message, bot: Bot):
    if not await is_owner(message.from_user.id):
        return

    data = await _read_uploaded_json(message, bot)
    if data is None:
        await message.answer(
            "Full export JSON pe reply karke <code>/import</code> bhejo.\n"
            "(<code>/export</code> se banayi gayi file hi use karo)"
        )
        return

    try:
        await db.import_all_config(data)
        count = len(data.get("groups", []))
        await message.answer(f"✅ Import complete! {count} groups restore ho gaye.")
        await db.log_owner_action(message.from_user.id, "import", f"{count} groups")
    except Exception as e:
        await message.answer(f"❌ Import fail hua: file format sahi nahi hai.\n{e}")


# ---------- Clone settings ----------

@router.message(Command("clonewelcome"))
async def cmd_clonewelcome(message: Message, command: CommandObject, bot: Bot):
    if not await is_owner(message.from_user.id):
        return

    target = (command.args or "").strip()
    if not target.lstrip("-").isdigit():
        await message.answer(
            "Target group ki chat_id do: <code>/clonewelcome -100123456789</code>\n"
            "(chat_id /groups command se milegi)"
        )
        return

    target_id = int(target)
    config = await db.export_chat_config(message.chat.id)
    await db.ensure_chat_row(target_id, "")
    await db.import_chat_config(target_id, config)
    await message.answer(f"✅ Welcome config <code>{message.chat.id}</code> se <code>{target_id}</code> mein clone ho gaya.")
    await db.log_owner_action(message.from_user.id, "clone_welcome", f"{message.chat.id} -> {target_id}")
