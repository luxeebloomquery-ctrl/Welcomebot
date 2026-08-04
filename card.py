from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from utils.admin import is_admin
from utils.card import THEMES

router = Router()


@router.message(Command("togglecard"))
async def cmd_togglecard(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    arg = (command.args or "").strip().lower()
    if arg == "on":
        await db.set_welcome_card(message.chat.id, True)
        await message.answer("🖼 Welcome Card ON — ab har naye member ke liye image card banega.")
    elif arg == "off":
        await db.set_welcome_card(message.chat.id, False)
        await message.answer("Welcome Card OFF — normal text/media welcome use hoga.")
    else:
        await message.answer("Use: <code>/togglecard on</code> ya <code>/togglecard off</code>")


@router.message(Command("theme"))
async def cmd_theme(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    arg = (command.args or "").strip().lower()
    if arg not in THEMES:
        available = ", ".join(THEMES.keys())
        await message.answer(f"Available themes: {available}\nUse: <code>/theme blue</code>")
        return

    await db.set_welcome_theme(message.chat.id, arg)
    await message.answer(f"🎨 Theme '<b>{arg}</b>' set ho gaya. Welcome card iske colors use karega.")
