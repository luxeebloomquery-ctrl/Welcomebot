from aiogram.types import LinkPreviewOptions
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, ChatMemberUpdated, BufferedInputFile
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION




import asyncio
import json

import database as db
from utils.admin import is_admin
from utils.buttons import extract_buttons, buttons_to_json, buttons_from_json, build_keyboard
from utils.placeholders import apply_placeholders
from utils.progress import ProgressMessage
from utils.video import process_video
from utils.card import generate_welcome_card
from handlers.album import build_album_media

router = Router()
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Welcome!\n\n"
        "Ye Welcome Bot hai.\n"
        "Commands dekhne ke liye /help use kare."  
    )

HELP_TEXT = (
    "<b>Welcome Bot — Commands</b>\n\n"
    "/welcome on|off - Welcome message chalu/band karo\n"
    "/setwelcome &lt;text&gt; - Naya welcome message set karo (media pe reply karke bhi chalega)\n"
    "/setalbum - Multi-media album (max 9 photo/video mixed) collect karna start karo\n"
    "/done &lt;caption&gt; - Album collection finish karo (sirf /setalbum ke baad)\n"
    "/cancel - Album collection cancel karo\n"
    "/resetwelcome - Default welcome message pe wapas jao\n"
    "/savetemplate &lt;naam&gt; - Current welcome ko template save karo\n"
    "/templates - Saare templates list karo\n"
    "/loadtemplate &lt;naam&gt; - Template ko active karo\n"
    "/deltemplate &lt;naam&gt; - Template delete karo\n"
    "/randomwelcome on|off - Har join pe random template use karo\n"
    "/listbuttons /removebutton &lt;text&gt; /previewbuttons - Button editor\n"
    "/addmedia /removemedia &lt;i&gt; /replacemedia &lt;i&gt; /reordermedia &lt;order&gt; /listmedia - Media editor\n"
    "/autodelete &lt;sec&gt; - Welcome N sec baad auto-delete\n"
    "/welcomedelay &lt;sec&gt; - Welcome N sec delay se bhejo\n"
    "/goodbye on|off /setgoodbye - Goodbye message (leave event pe)\n"
    "/togglecard on|off /theme &lt;naam&gt; - Image welcome card + themes (blue/dark/sunset/forest/purple)\n"
    "/cleanservice on|off - Telegram ke \"X joined/left\" messages auto-delete\n"
    "/backup /restore - Is group ka config JSON file mein save/restore karo\n\n"
    "<b>Owner-only:</b> /export /import /clonewelcome /addowner /removeowner /owners /ownerlogs\n"
    "/builder - Interactive button-based welcome editor\n"
    "/scheduletemplate /templateschedules - Date-based automatic template switching\n"
    "<b>Owner-only:</b> /schedulebroadcast /pendingbroadcasts /cancelbroadcast /health\n"
    "/preview - Abhi ka welcome message dekho\n"
    "/settings - Is group ki current settings dekho\n"
    "/help - Ye message\n\n"
    "<b>Placeholders:</b> {first} {last} {fullname} {username} {mention} {id} {chatname} {count}\n\n"
    "<b>Button syntax:</b>\n"
    "<code>[Button Text](buttonurl:https://example.com)</code>\n"
    "Same row mein 2 buttons ke liye pehle button ke end mein <code>:same</code> lagao."
)


def _media_type_and_id(message: Message):
    """Reply ki gayi message se media type aur file_id nikalta hai."""
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
    await message.answer(HELP_TEXT)


@router.message(Command("settings"))
async def cmd_settings(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
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
    await message.answer(text)


@router.message(Command("welcome"))
async def cmd_welcome_toggle(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    arg = (command.args or "").strip().lower()

    if arg == "on":
        await db.set_enabled(message.chat.id, True)
        await message.answer("✅ Welcome message chalu kar diya gaya.")
    elif arg == "off":
        await db.set_enabled(message.chat.id, False)
        await message.answer("❌ Welcome message band kar diya gaya.")
    else:
        settings = await db.get_settings(message.chat.id)
        status = "ON ✅" if settings["enabled"] else "OFF ❌"
        await message.answer(
            f"Welcome abhi <b>{status}</b> hai.\nUse: <code>/welcome on</code> ya <code>/welcome off</code>"
        )


@router.message(Command("setwelcome"))
async def cmd_setwelcome(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")

    # Reply kiye gaye media se text nikalna, ya command args se
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
            "Example: <code>/setwelcome Welcome {mention} to {chatname}!</code>"
        )
        return

    clean_text, button_rows = extract_buttons(raw_text)
    buttons_json = buttons_to_json(button_rows)

    if not clean_text:
        clean_text = db.DEFAULT_TEXT if not file_id else ""

    if file_id and media_type:
        if media_type == "video":
            progress = ProgressMessage(bot, message.chat.id)
            await progress.start("🎬 Video process ho raha hai...")
            file_id = await process_video(bot, message.chat.id, file_id, progress)
        await db.set_welcome_media(message.chat.id, clean_text, buttons_json, file_id, media_type)
    else:
        await db.set_welcome_text(message.chat.id, clean_text, buttons_json)

    await message.answer("✅ Welcome message set ho gaya! Check karne ke liye /preview use karo.")


@router.message(Command("resetwelcome"))
async def cmd_resetwelcome(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    await db.reset_welcome(message.chat.id)
    await message.answer("♻️ Welcome message default pe reset ho gaya.")


@router.message(Command("preview"))
async def cmd_preview(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return

    settings = await db.get_settings(message.chat.id)
    member_count = await db.get_member_count_placeholder(bot, message.chat.id)
    text = apply_placeholders(settings["text"], message.from_user, message.chat, member_count)
    keyboard = build_keyboard(buttons_from_json(settings["buttons"]))

    await _send_welcome(message.chat.id, bot, settings, text, keyboard)


async def _send_welcome(chat_id: int, bot: Bot, settings: dict, text: str, keyboard) -> list[int]:
    """Type ke hisab se sahi media method call karta hai. Sent message IDs return karta hai."""
    sent_ids = []

    # Album (multi-media) sabse pehle check karo
    if settings.get("album_json"):
        items = json.loads(settings["album_json"])
        media = build_album_media(items, text)
        msgs = await bot.send_media_group(chat_id, media)
        sent_ids.extend(m.message_id for m in msgs)
        # Telegram media groups mein inline buttons nahi lagte, isliye alag message
        if keyboard:
            btn_msg = await bot.send_message(
    chat_id,
    "👇",
    reply_markup=keyboard,
    link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            sent_ids.append(btn_msg.message_id)
        return sent_ids

    media_type = settings["media_type"]
    file_id = settings["media_file_id"]

    if media_type == "photo":
        msg = await bot.send_photo(chat_id, file_id, caption=text, reply_markup=keyboard)
    elif media_type == "video":
        msg = await bot.send_video(chat_id, file_id, caption=text, reply_markup=keyboard)
    elif media_type == "animation":
        msg = await bot.send_animation(chat_id, file_id, caption=text, reply_markup=keyboard)
    elif media_type == "sticker":
        sticker_msg = await bot.send_sticker(chat_id, file_id)
        sent_ids.append(sticker_msg.message_id)
        msg = None
        if text.strip():
            msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
    elif media_type == "document":
        msg = await bot.send_document(chat_id, file_id, caption=text, reply_markup=keyboard)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)

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
    msg = await bot.send_photo(chat.id, photo, caption=text, reply_markup=keyboard)
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

    # Random welcome: multiple templates mein se ek random pick karo
    send_settings = settings
    if settings.get("random_welcome"):
        tpl = await db.get_random_template(chat.id)
        if tpl:
            send_settings = {**settings, **tpl}

    member_count = await db.get_member_count_placeholder(bot, chat.id)
    text = apply_placeholders(send_settings["text"], user, chat, member_count)
    keyboard = build_keyboard(buttons_from_json(send_settings["buttons"]))

    try:
        if settings.get("welcome_card"):
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
    """Bot admin ho to ye trigger hota hai (zyada reliable, silent joins bhi pakadta hai)."""
    await _handle_new_member(event.chat, event.new_chat_member.user, bot)


@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot):
    """Fallback: bot admin na ho tab bhi ye service message se new members pakad leta hai."""
    for user in message.new_chat_members:
        await _handle_new_member(message.chat, user, bot)

    # Clean service message: Telegram ka native "X joined" message delete karo agar setting on hai
    settings = await db.get_settings(message.chat.id)
    if settings.get("clean_service"):
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
