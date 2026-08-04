from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from utils.admin import is_admin

router = Router()


@router.message(Command("savetemplate"))
async def cmd_savetemplate(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    name = (command.args or "").strip()
    if not name:
        await message.answer("Template ka naam do: <code>/savetemplate diwali</code>")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    await db.save_template(message.chat.id, name)
    await message.answer(f"✅ Current welcome '<b>{name}</b>' naam se template mein save ho gaya.")


@router.message(Command("templates"))
async def cmd_templates(message: Message):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return

    templates = await db.list_templates(message.chat.id)
    if not templates:
        await message.answer("Koi template save nahi hai. <code>/savetemplate naam</code> use karo.")
        return

    lines = "\n".join(f"• {t['name']}" for t in templates)
    await message.answer(f"<b>📁 Saved Templates ({len(templates)})</b>\n\n{lines}")


@router.message(Command("loadtemplate"))
async def cmd_loadtemplate(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    name = (command.args or "").strip()
    if not name:
        await message.answer("Template ka naam do: <code>/loadtemplate diwali</code>")
        return

    ok = await db.load_template(message.chat.id, name)
    if ok:
        await message.answer(f"✅ Template '<b>{name}</b>' active welcome bana diya gaya. /preview se check karo.")
    else:
        await message.answer(f"❌ '{name}' naam ka template nahi mila. /templates se list dekho.")


@router.message(Command("deltemplate"))
async def cmd_deltemplate(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    name = (command.args or "").strip()
    if not name:
        await message.answer("Template ka naam do: <code>/deltemplate diwali</code>")
        return

    ok = await db.delete_template(message.chat.id, name)
    if ok:
        await message.answer(f"🗑 Template '<b>{name}</b>' delete kar diya gaya.")
    else:
        await message.answer(f"❌ '{name}' naam ka template nahi mila.")


@router.message(Command("randomwelcome"))
async def cmd_randomwelcome(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    arg = (command.args or "").strip().lower()
    if arg == "on":
        templates = await db.list_templates(message.chat.id)
        if not templates:
            await message.answer("Pehle kam se kam ek template save karo (<code>/savetemplate naam</code>).")
            return
        await db.set_random_mode(message.chat.id, True)
        await message.answer(f"🎲 Random welcome ON — {len(templates)} templates mein se random pick hoga.")
    elif arg == "off":
        await db.set_random_mode(message.chat.id, False)
        await message.answer("Random welcome OFF — normal active welcome use hoga.")
    else:
        await message.answer("Use: <code>/randomwelcome on</code> ya <code>/randomwelcome off</code>")
