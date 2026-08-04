import json

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from utils.admin import is_admin
from utils.buttons import buttons_from_json, buttons_to_json, build_keyboard
from utils.progress import ProgressMessage
from utils.video import process_video

router = Router()

MAX_MEDIA = 9


# ---------- Button Editor ----------

@router.message(Command("listbuttons"))
async def cmd_listbuttons(message: Message):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    settings = await db.get_settings(message.chat.id)
    rows = buttons_from_json(settings["buttons"])
    if not rows:
        await message.answer("Koi button set nahi hai.")
        return
    lines = []
    for row in rows:
        lines.append(" | ".join(f"{b['text']} → {b['url']}" for b in row))
    await message.answer("<b>🔘 Current Buttons</b>\n\n" + "\n".join(lines))


@router.message(Command("removebutton"))
async def cmd_removebutton(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    target = (command.args or "").strip().lower()
    if not target:
        await message.answer("Button ka text do: <code>/removebutton Rules</code>")
        return

    settings = await db.get_settings(message.chat.id)
    rows = buttons_from_json(settings["buttons"])
    if not rows:
        await message.answer("Koi button set nahi hai.")
        return

    new_rows = []
    removed = False
    for row in rows:
        new_row = [b for b in row if b["text"].lower() != target]
        removed = removed or (len(new_row) != len(row))
        if new_row:
            new_rows.append(new_row)

    if not removed:
        await message.answer(f"❌ '{target}' naam ka button nahi mila.")
        return

    await db.update_buttons_json(message.chat.id, buttons_to_json(new_rows) if new_rows else None)
    await message.answer(f"✅ Button '{target}' remove kar diya gaya.")


@router.message(Command("previewbuttons"))
async def cmd_previewbuttons(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    settings = await db.get_settings(message.chat.id)
    keyboard = build_keyboard(buttons_from_json(settings["buttons"]))
    if not keyboard:
        await message.answer("Koi button set nahi hai.")
        return
    await bot.send_message(message.chat.id, "🔘 Button preview:", reply_markup=keyboard)


# ---------- Media Editor (album items) ----------

def _media_type_and_id(message: Message):
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    return None, None


@router.message(Command("addmedia"))
async def cmd_addmedia(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    reply = message.reply_to_message
    if not reply:
        await message.answer("Photo/video pe reply karke <code>/addmedia</code> bhejo.")
        return

    media_type, file_id = _media_type_and_id(reply)
    if not media_type:
        await message.answer("Sirf photo ya video reply karo.")
        return

    settings = await db.get_settings(message.chat.id)
    items = json.loads(settings["album_json"]) if settings["album_json"] else []

    if len(items) >= MAX_MEDIA:
        await message.answer(f"⚠️ Album already {MAX_MEDIA} items pe full hai. Pehle kuch remove karo.")
        return

    if media_type == "video":
        progress = ProgressMessage(bot, message.chat.id)
        await progress.start("🎬 Video process ho raha hai...")
        file_id = await process_video(bot, message.chat.id, file_id, progress)

    items.append({"type": media_type, "file_id": file_id})
    await db.update_album_json(message.chat.id, json.dumps(items))
    await message.answer(f"✅ Media add ho gaya. Total: {len(items)}/{MAX_MEDIA}")


@router.message(Command("removemedia"))
async def cmd_removemedia(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    settings = await db.get_settings(message.chat.id)
    items = json.loads(settings["album_json"]) if settings["album_json"] else []

    idx_str = (command.args or "").strip()
    if not idx_str.isdigit():
        await message.answer("Index do (1-based): <code>/removemedia 3</code>\nSaari list ke liye /listmedia use karo.")
        return

    idx = int(idx_str) - 1
    if idx < 0 or idx >= len(items):
        await message.answer(f"❌ Invalid index. Album mein {len(items)} items hai.")
        return

    removed = items.pop(idx)
    await db.update_album_json(message.chat.id, json.dumps(items) if items else None)
    await message.answer(f"🗑 Item {idx+1} ({removed['type']}) remove ho gaya. Baaki: {len(items)}")


@router.message(Command("replacemedia"))
async def cmd_replacemedia(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    reply = message.reply_to_message
    if not reply:
        await message.answer("Naye photo/video pe reply karke <code>/replacemedia 2</code> bhejo.")
        return

    idx_str = (command.args or "").strip()
    if not idx_str.isdigit():
        await message.answer("Index do (1-based): naye media pe reply karke <code>/replacemedia 2</code>")
        return

    media_type, file_id = _media_type_and_id(reply)
    if not media_type:
        await message.answer("Sirf photo ya video reply karo.")
        return

    settings = await db.get_settings(message.chat.id)
    items = json.loads(settings["album_json"]) if settings["album_json"] else []
    idx = int(idx_str) - 1
    if idx < 0 or idx >= len(items):
        await message.answer(f"❌ Invalid index. Album mein {len(items)} items hai.")
        return

    if media_type == "video":
        progress = ProgressMessage(bot, message.chat.id)
        await progress.start("🎬 Video process ho raha hai...")
        file_id = await process_video(bot, message.chat.id, file_id, progress)

    items[idx] = {"type": media_type, "file_id": file_id}
    await db.update_album_json(message.chat.id, json.dumps(items))
    await message.answer(f"✅ Item {idx+1} replace ho gaya.")


@router.message(Command("reordermedia"))
async def cmd_reordermedia(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    settings = await db.get_settings(message.chat.id)
    items = json.loads(settings["album_json"]) if settings["album_json"] else []
    if not items:
        await message.answer("Album khali hai.")
        return

    order_str = (command.args or "").strip()
    if not order_str:
        await message.answer(
            f"Naya order do comma-separated (1-based), jaise <code>/reordermedia 3,1,2</code>\n"
            f"Abhi {len(items)} items hai."
        )
        return

    try:
        order = [int(x.strip()) - 1 for x in order_str.split(",")]
    except ValueError:
        await message.answer("Sirf numbers do, comma se separate karke. Jaise: 3,1,2")
        return

    if sorted(order) != list(range(len(items))):
        await message.answer(f"❌ Order mein sab {len(items)} indices exactly ek baar honi chahiye (1 se {len(items)}).")
        return

    new_items = [items[i] for i in order]
    await db.update_album_json(message.chat.id, json.dumps(new_items))
    await message.answer("✅ Media order update ho gaya.")


@router.message(Command("listmedia"))
async def cmd_listmedia(message: Message):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    settings = await db.get_settings(message.chat.id)
    items = json.loads(settings["album_json"]) if settings["album_json"] else []
    if not items:
        await message.answer("Album khali hai.")
        return
    lines = "\n".join(f"{i+1}. {it['type']}" for i, it in enumerate(items))
    await message.answer(f"<b>🖼 Album Items ({len(items)}/{MAX_MEDIA})</b>\n\n{lines}")


# ---------- Auto-delete / Welcome delay ----------

@router.message(Command("autodelete"))
async def cmd_autodelete(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer(
            "Seconds do, 0 = off. Jaise: <code>/autodelete 60</code> (1 min baad welcome delete hoga)"
        )
        return

    seconds = int(arg)
    await db.set_auto_delete(message.chat.id, seconds)
    if seconds == 0:
        await message.answer("Auto-delete OFF kar diya gaya.")
    else:
        await message.answer(f"✅ Welcome message ab {seconds} second baad auto-delete hoga.")


# ---------- Clean Service Messages ----------

@router.message(Command("cleanservice"))
async def cmd_cleanservice(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    arg = (command.args or "").strip().lower()
    if arg == "on":
        await db.set_clean_service(message.chat.id, True)
        await message.answer("🧹 Clean service messages ON — Telegram ke \"X joined/left\" messages auto-delete honge.")
    elif arg == "off":
        await db.set_clean_service(message.chat.id, False)
        await message.answer("Clean service messages OFF.")
    else:
        await message.answer("Use: <code>/cleanservice on</code> ya <code>/cleanservice off</code>")


@router.message(Command("welcomedelay"))
async def cmd_welcomedelay(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer(
            "Seconds do, 0 = turant. Jaise: <code>/welcomedelay 5</code> (5 sec baad welcome bhejega)"
        )
        return

    seconds = int(arg)
    await db.set_welcome_delay(message.chat.id, seconds)
    if seconds == 0:
        await message.answer("Welcome delay OFF — turant bhejega.")
    else:
        await message.answer(f"✅ Welcome ab join ke {seconds} second baad bhejega.")
