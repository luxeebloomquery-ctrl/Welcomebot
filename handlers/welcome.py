import asyncio
import json

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.filters.chat_member_updated import JOIN_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import BufferedInputFile, ChatMemberUpdated, LinkPreviewOptions, Message

import database as db
from handlers.album import build_album_media
from utils.admin import is_admin
from utils.buttons import build_keyboard, buttons_from_json, buttons_to_json, extract_buttons
from utils.card import generate_welcome_card
from utils.placeholders import apply_placeholders

router = Router()


def get_link_preview_config():
    return LinkPreviewOptions(is_disabled=True)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Welcome!\n\nYe Welcome Bot hai.\nCommands dekhne ke liye /help use kare.",
        link_preview_options=get_link_preview_config(),
    )


HELP_TEXT = (
    "<b>Welcome Bot — Commands</b>\n\n"
    "/welcome on|off - Welcome message chalu/band karo\n"
    "/setwelcome &lt;text&gt; - Naya welcome message set karo (media pe reply karke bhi chalega)\n"
    "/setalbum - Multi-media album collect karna start karo\n"
    "/done &lt;caption&gt; - Album collection finish karo\n"
    "/cancel - Album collection cancel karo\n"
    "/resetwelcome - Default welcome message pe wapas jao\n"
    "/savetemplate &lt;naam&gt; - Current welcome ko template save karo\n"
    "/templates - Saare templates list karo\n"
    "/loadtemplate &lt;naam&gt; - Template ko active karo\n"
    "/deltemplate &lt;naam&gt; - Template delete karo\n"
    "/randomwelcome on|off - Har join pe random template use karo\n"
    "/preview - Abhi ka welcome message dekho\n"
    "/settings - Is group ki current settings dekho\n"
    "/help - Ye message\n\n"
    "<b>Placeholders:</b> {first} {last} {fullname} {username} {mention} {id} {chatname} {count}\n\n"
    "<b>Button syntax:</b>\n"
    "<code>[Button Text](buttonurl:https://example.com)</code>"
)


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


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", link_preview_options=get_link_preview_config())


@router.message(Command("settings"))
async def cmd_settings(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=get_link_preview_config())
        return
    settings = await db.get_settings(message.chat.id)
    status = "✅ ON" if settings["enabled"] else "❌ OFF"
    if settings.get("album_json"):
        media_info = f"Album ({len(json.loads(settings['album_json']))} items)"
    else:
        media_info = settings["media_type"] or "None"
    text = (
        f"<b>Welcome Settings — {settings['chat_name'] or message.chat.title}</b>\n\n"
        f"Status: {status}\n"
        f"Media: {media_info}\n"
        f"Buttons: {'Yes' if settings['buttons'] else 'No'}\n\n"
        f"Preview ke liye /preview use karo."
    )
    await message.answer(text, parse_mode="HTML", link_preview_options=get_link_preview_config())


@router.message(Command("welcome"))
async def cmd_welcome_toggle(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=get_link_preview_config())
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.", link_preview_options=get_link_preview_config())
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    arg = (command.args or "").strip().lower()

    if arg == "on":
        await db.set_enabled(message.chat.id, True)
        await message.answer("✅ Welcome message chalu kar diya gaya.", link_preview_options=get_link_preview_config())
    elif arg == "off":
        await db.set_enabled(message.chat.id, False)
        await message.answer("❌ Welcome message band kar diya gaya.", link_preview_options=get_link_preview_config())
    else:
        settings = await db.get_settings(message.chat.id)
        status = "ON ✅" if settings["enabled"] else "OFF ❌"
        await message.answer(
            f"Welcome abhi <b>{status}</b> hai.\nUse: <code>/welcome on</code> ya <code>/welcome off</code>",
            parse_mode="HTML",
            link_preview_options=get_link_preview_config(),
        )


@router.message(Command("setwelcome"))
@router.message(F.caption.contains("/setwelcome"))
async def cmd_setwelcome(message: Message, command: CommandObject = None, bot: Bot = None):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=get_link_preview_config())
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.", link_preview_options=get_link_preview_config())
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")

    reply = message.reply_to_message
    media_type, file_id = None, None
    raw_text = command.args if (command and command.args) else ""

    if message.photo:
        media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        media_type, file_id = "video", message.video.file_id
    elif message.animation:
        media_type, file_id = "animation", message.animation.file_id
    elif message.document:
        media_type, file_id = "document", message.document.file_id

    if message.caption and not raw_text:
        caption_text = message.caption
        if "/setwelcome" in caption_text:
            raw_text = caption_text.split("/setwelcome", 1)[1].strip()
        else:
            raw_text = caption_text.strip()

    if not file_id and reply:
        media_type, file_id = _media_type_and_id(reply)
        if reply.caption and not raw_text:
            raw_text = reply.caption
        elif reply.text and not raw_text:
            raw_text = reply.text

    if not raw_text and not file_id:
        await message.answer(
            "Kuch text do ya media pe reply karke caption ke sath likho.\n"
            "Example: <code>/setwelcome Welcome {mention} to {chatname}!</code>",
            parse_mode="HTML",
            link_preview_options=get_link_preview_config(),
        )
        return

    clean_text, button_rows = extract_buttons(raw_text)
    buttons_json = buttons_to_json(button_rows)

    if not clean_text:
        clean_text = db.DEFAULT_TEXT if not file_id else ""

    if file_id:
        await db.set_welcome_card(message.chat.id, False)

    if file_id and media_type:
        await db.set_welcome_media(message.chat.id, clean_text, buttons_json, file_id, media_type)
    else:
        await db.set_welcome_text(message.chat.id, clean_text, buttons_json)

    await message.answer("✅ Welcome message set ho gaya! Check karne ke liye /preview use karo.", link_preview_options=get_link_preview_config())


@router.message(Command("resetwelcome"))
async def cmd_resetwelcome(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=get_link_preview_config())
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.", link_preview_options=get_link_preview_config())
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    await db.reset_welcome(message.chat.id)
    await message.answer("♻️ Welcome message default pe reset ho gaya.", link_preview_options=get_link_preview_config())


@router.message(Command("preview"))
async def cmd_preview(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=get_link_preview_config())
        return

    settings = await db.get_settings(message.chat.id)
    member_count = await db.get_member_count_placeholder(bot, message.chat.id)
    text = apply_placeholders(settings["text"], message.from_user, message.chat, member_count)
    keyboard = build_keyboard(buttons_from_json(settings["buttons"]))

    await _send_welcome(message.chat.id, bot, settings, text, keyboard)


async def _send_welcome(chat_id: int, bot: Bot, settings: dict, text: str, keyboard) -> list[int]:
    sent_ids = []

    if settings.get("album_json"):
        items = json.loads(settings["album_json"])
        media = build_album_media(items, text)
        msgs = await bot.send_media_group(chat_id, media)
        sent_ids.extend(m.message_id for m in msgs)
        if keyboard:
            btn_msg = await bot.send_message(
                chat_id,
                "👇",
                reply_markup=keyboard,
                link_preview_options=get_link_preview_config(),
            )
            sent_ids.append(btn_msg.message_id)
        return sent_ids

    media_type = settings["media_type"]
    file_id = settings["media_file_id"]

    try:
        if media_type == "photo" and file_id:
            msg = await bot.send_photo(chat_id, file_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
        elif media_type == "video" and file_id:
            msg = await bot.send_video(chat_id, file_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
        elif media_type == "animation" and file_id:
            msg = await bot.send_animation(chat_id, file_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
        elif media_type == "sticker" and file_id:
            sticker_msg = await bot.send_sticker(chat_id, file_id)
            sent_ids.append(sticker_msg.message_id)
            msg = None
            if text.strip():
                msg = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML", link_preview_options=get_link_preview_config())
        elif media_type == "document" and file_id:
            msg = await bot.send_document(chat_id, file_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            msg = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML", link_preview_options=get_link_preview_config())

        if msg:
            sent_ids.append(msg.message_id)
    except Exception:
        if media_type == "video" and file_id:
            msg = await bot.send_video(chat_id, file_id, caption=text, reply_markup=keyboard)
        else:
            msg = await bot.send_message(chat_id, text, reply_markup=keyboard, link_preview_options=get_link_preview_config())
        if msg:
            sent_ids.append(msg.message_id)

    return sent_ids


async def _get_avatar_bytes(bot: Bot, user_id: int) -> bytes | None:
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count == 0:
            return None
        file_id = photos.photos[0][-1].file_id
        buf = await bot.download(file_id)
        return buf.read() if buf else None
    except Exception:
        return None


async def _send_welcome_card(chat, user, bot: Bot, settings: dict, member_count: int, text: str, keyboard) -> list[int]:
    avatar_bytes = await _get_avatar_bytes(bot, user.id)
    card_bytes = generate_welcome_card(
        user.first_name or "User",
        chat.title or "this group",
        member_count,
        theme=settings.get("welcome_theme") or "blue",
        avatar_bytes=avatar_bytes,
    )
    photo = BufferedInputFile(card_bytes, filename="welcome_card.png")
    msg = await bot.send_photo(chat.id, photo, caption=text, reply_markup=keyboard, parse_mode="HTML")
    return [msg.message_id]


async def _handle_new_member(chat, user, bot: Bot):
    if user.is_bot:
        return

    await db.ensure_chat_row(chat.id, chat.title or "")
    settings = await db.get_settings(chat.id)

    if not settings["enabled"]:
        return

    delay = settings.get("welcome_delay_seconds") or 0
    if delay > 0:
        await asyncio.sleep(delay)

    send_settings = settings
    if settings.get("random_welcome"):
        tpl = await db.get_random_template(chat.id)
        if tpl:
            send_settings = {**settings, **tpl}

    member_count = await db.get_member_count_placeholder(bot, chat.id)
    text = apply_placeholders(send_settings["text"], user, chat, member_count)
    keyboard = build_keyboard(buttons_from_json(send_settings["buttons"]))

    try:
        if settings.get("welcome_card") and not send_settings.get("media_file_id"):
            sent_ids = await _send_welcome_card(chat, user, bot, settings, member_count, text, keyboard)
        else:
            sent_ids = await _send_welcome(chat.id, bot, send_settings, text, keyboard)

        auto_delete = settings.get("auto_delete_seconds") or 0
        if auto_delete > 0 and sent_ids:
            asyncio.create_task(_delayed_delete(bot, chat.id, sent_ids, auto_delete))
    except Exception as e:
        print(f"Welcome message bhejne mein error chat {chat.id}: {e}")


async def _delayed_delete(bot: Bot, chat_id: int, message_ids: list[int], delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated, bot: Bot):
    await _handle_new_member(event.chat, event.new_chat_member.user, bot)


@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot):
    for user in message.new_chat_members:
        await _handle_new_member(message.chat, user, bot)

    settings = await db.get_settings(message.chat.id)
    if settings.get("clean_service"):
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
    
