import json

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo

import database as db
from utils.admin import is_admin
from utils.buttons import extract_buttons, buttons_to_json
from utils.progress import ProgressMessage
from utils.video import process_video

router = Router()

MAX_MEDIA = 9


class AlbumStates(StatesGroup):
    collecting = State()


def _media_type_and_id(message: Message):
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    return None, None


@router.message(Command("setalbum"))
async def cmd_setalbum(message: Message, state: FSMContext, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")

    progress = ProgressMessage(bot, message.chat.id)
    await progress.start("📸 <b>Album collection shuru!</b>\nPhotos/videos bhejo (max 9, mixed allowed).", 0)

    await state.set_state(AlbumStates.collecting)
    await state.update_data(
        items=[],
        progress_message_id=progress.message_id,
        admin_id=message.from_user.id,
    )
    await message.answer(
        "Jab saara media bhej do, caption ke sath <code>/done Welcome {mention}!</code> bhejo.\n"
        "Cancel karne ke liye /cancel."
    )


@router.message(StateFilter(AlbumStates.collecting), F.photo | F.video)
async def collect_media(message: Message, state: FSMContext, bot: Bot):
    # Sirf wahi admin add kar sakta hai jisne /setalbum start kiya
    data = await state.get_data()
    if message.from_user.id != data.get("admin_id"):
        return

    media_type, file_id = _media_type_and_id(message)
    if not media_type:
        return

    items = data.get("items", [])

    if len(items) >= MAX_MEDIA:
        await message.reply(f"⚠️ Max {MAX_MEDIA} media limit ho gayi hai. Ye extra ignore kar diya. /done bhejo.")
        return

    progress = ProgressMessage(bot, message.chat.id)
    progress.message_id = data.get("progress_message_id")

    # Video 20 sec se lamba ho to auto-trim (FFmpeg), progress bar isi message pe dikhta hai
    if media_type == "video":
        file_id = await process_video(bot, message.chat.id, file_id, progress)

    items.append({"type": media_type, "file_id": file_id})
    await state.update_data(items=items)

    photos = sum(1 for i in items if i["type"] == "photo")
    videos = sum(1 for i in items if i["type"] == "video")
    percent = round((len(items) / MAX_MEDIA) * 100)

    await progress.update(
        percent,
        f"📸 <b>Collecting media...</b> ({len(items)}/{MAX_MEDIA})\n"
        f"Photos: {photos} | Videos: {videos}",
        force=True,
    )


@router.message(StateFilter(AlbumStates.collecting), Command("done"))
async def finish_album(message: Message, state: FSMContext, command: CommandObject, bot: Bot):
    data = await state.get_data()
    if message.from_user.id != data.get("admin_id"):
        return

    items = data.get("items", [])
    if not items:
        await message.answer("Koi media collect nahi hua. Pehle photos/videos bhejo ya /cancel karo.")
        return

    raw_caption = command.args or "Welcome {mention} to {chatname}! 🎉"
    clean_text, button_rows = extract_buttons(raw_caption)
    buttons_json = buttons_to_json(button_rows)

    album_json = json.dumps(items)
    await db.set_welcome_album(message.chat.id, album_json, clean_text, buttons_json)

    progress = ProgressMessage(bot, message.chat.id)
    progress.message_id = data.get("progress_message_id")
    await progress.finish(f"✅ <b>Album saved!</b> {len(items)} media items.\nCheck karne ke liye /preview use karo.")

    await state.clear()


@router.message(StateFilter(AlbumStates.collecting), Command("cancel"))
async def cancel_album(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get("admin_id"):
        return
    await state.clear()
    await message.answer("❌ Album collection cancel kar diya gaya.")


def build_album_media(items: list[dict], caption: str):
    """DB se aaye album items ko send_media_group ke liye InputMedia list mein convert karta hai.
    Caption sirf pehle item pe lagta hai (Telegram ka rule)."""
    media = []
    for idx, item in enumerate(items):
        cap = caption if idx == 0 else None
        if item["type"] == "photo":
            media.append(InputMediaPhoto(media=item["file_id"], caption=cap))
        elif item["type"] == "video":
            media.append(InputMediaVideo(media=item["file_id"], caption=cap))
    return media
