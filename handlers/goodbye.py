from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, LEAVE_TRANSITION
from aiogram.types import Message, ChatMemberUpdated

import database as db
from utils.admin import is_admin
from utils.buttons import extract_buttons, buttons_to_json, buttons_from_json, build_keyboard
from utils.placeholders import apply_placeholders

router = Router()


def _media_type_and_id(message: Message):
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    if message.animation:
        return "animation", message.animation.file_id
    if message.sticker:
        return "sticker", message.sticker.file_id
    if message.document:
        return "document", message.document.file_id
    return None, None


@router.message(Command("goodbye"))
async def cmd_goodbye_toggle(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    arg = (command.args or "").strip().lower()

    if arg == "on":
        await db.set_goodbye_enabled(message.chat.id, True)
        await message.answer("✅ Goodbye message chalu kar diya gaya.")
    elif arg == "off":
        await db.set_goodbye_enabled(message.chat.id, False)
        await message.answer("❌ Goodbye message band kar diya gaya.")
    else:
        settings = await db.get_goodbye_settings(message.chat.id)
        status = "ON ✅" if settings["enabled"] else "OFF ❌"
        await message.answer(
            f"Goodbye abhi <b>{status}</b> hai.\nUse: <code>/goodbye on</code> ya <code>/goodbye off</code>"
        )


@router.message(Command("setgoodbye"))
async def cmd_setgoodbye(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")

    reply = message.reply_to_message
    media_type, file_id = (None, None)
    raw_text = command.args or ""

    if reply:
        media_type, file_id = _media_type_and_id(reply)
        if reply.caption:
            raw_text = reply.caption
        elif reply.text and not raw_text:
            raw_text = reply.text

    if not raw_text and not file_id:
        await message.answer(
            "Kuch text do ya media pe reply karke caption ke sath likho.\n"
            "Example: <code>/setgoodbye Bye {first}, take care!</code>"
        )
        return

    clean_text, button_rows = extract_buttons(raw_text)
    buttons_json = buttons_to_json(button_rows)

    if not clean_text:
        clean_text = db.DEFAULT_GOODBYE if not file_id else ""

    if file_id and media_type:
        await db.set_goodbye_media(message.chat.id, clean_text, buttons_json, file_id, media_type)
    else:
        await db.set_goodbye_text(message.chat.id, clean_text, buttons_json)

    await message.answer("✅ Goodbye message set ho gaya!")


async def _send_goodbye(chat_id: int, bot: Bot, settings: dict, text: str, keyboard):
    media_type = settings["media_type"]
    file_id = settings["media_file_id"]

    if media_type == "photo":
        await bot.send_photo(chat_id, file_id, caption=text, reply_markup=keyboard)
    elif media_type == "video":
        await bot.send_video(chat_id, file_id, caption=text, reply_markup=keyboard)
    elif media_type == "animation":
        await bot.send_animation(chat_id, file_id, caption=text, reply_markup=keyboard)
    elif media_type == "sticker":
        await bot.send_sticker(chat_id, file_id)
        if text.strip():
            await bot.send_message(chat_id, text, reply_markup=keyboard)
    elif media_type == "document":
        await bot.send_document(chat_id, file_id, caption=text, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, text, reply_markup=keyboard)


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_user_leave(event: ChatMemberUpdated, bot: Bot):
    chat = event.chat
    user = event.old_chat_member.user
    if user.is_bot:
        return

    settings = await db.get_goodbye_settings(chat.id)
    if not settings["enabled"]:
        return

    member_count = await db.get_member_count_placeholder(bot, chat.id)
    text = apply_placeholders(settings["text"], user, chat, member_count)
    keyboard = build_keyboard(buttons_from_json(settings["buttons"]))

    try:
        await _send_goodbye(chat.id, bot, settings, text, keyboard)
    except Exception as e:
        print(f"Goodbye message bhejne mein error chat {chat.id}: {e}")


@router.message(F.left_chat_member)
async def on_left_chat_member(message: Message, bot: Bot):
    """Fallback: bot admin na ho tab bhi ye service message se leave pakad leta hai."""
    user = message.left_chat_member
    if user.is_bot:
        return

    settings = await db.get_goodbye_settings(message.chat.id)
    if settings["enabled"]:
        member_count = await db.get_member_count_placeholder(bot, message.chat.id)
        text = apply_placeholders(settings["text"], user, message.chat, member_count)
        keyboard = build_keyboard(buttons_from_json(settings["buttons"]))
        try:
            await _send_goodbye(message.chat.id, bot, settings, text, keyboard)
        except Exception as e:
            print(f"Goodbye message bhejne mein error chat {message.chat.id}: {e}")

    # Clean service message: Telegram ka native "X left" message delete karo agar setting on hai
    welcome_settings = await db.get_settings(message.chat.id)
    if welcome_settings.get("clean_service"):
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
