from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import database as db
from config import OWNER_ID
from utils.ownercheck import is_owner

router = Router()


@router.message(Command("addowner"))
async def cmd_addowner(message: Message, command: CommandObject):
    # Sirf super-owner (config.py wala OWNER_ID) naye owners add kar sakta hai
    if message.from_user.id != OWNER_ID:
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("User ki numeric Telegram ID do: <code>/addowner 123456789</code>")
        return

    new_owner_id = int(arg)
    await db.add_owner(new_owner_id, added_by=message.from_user.id)
    await db.log_owner_action(message.from_user.id, "add_owner", str(new_owner_id))
    await message.answer(f"✅ <code>{new_owner_id}</code> ab owner hai — Owner Panel commands use kar sakta hai.")


@router.message(Command("removeowner"))
async def cmd_removeowner(message: Message, command: CommandObject):
    if message.from_user.id != OWNER_ID:
        return

    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("User ki numeric Telegram ID do: <code>/removeowner 123456789</code>")
        return

    target_id = int(arg)
    ok = await db.remove_owner(target_id)
    if ok:
        await db.log_owner_action(message.from_user.id, "remove_owner", str(target_id))
        await message.answer(f"🗑 <code>{target_id}</code> ab owner nahi raha.")
    else:
        await message.answer("❌ Ye user owner nahi hai, ya wo super-owner hai (jo remove nahi ho sakta).")


@router.message(Command("owners"))
async def cmd_owners(message: Message):
    if not await is_owner(message.from_user.id):
        return

    owners = await db.list_owners()
    lines = "\n".join(f"• <code>{o}</code>" + (" (super-owner)" if o == OWNER_ID else "") for o in owners)
    await message.answer(f"<b>👑 Owners ({len(owners)})</b>\n\n{lines}")


@router.message(Command("ownerlogs"))
async def cmd_ownerlogs(message: Message):
    if not await is_owner(message.from_user.id):
        return

    logs = await db.get_owner_logs(15)
    if not logs:
        await message.answer("Koi owner action log nahi hai abhi tak.")
        return

    lines = []
    for log in logs:
        detail = f" — {log['details']}" if log["details"] else ""
        lines.append(f"• [{log['created_at']}] {log['user_id']}: <b>{log['action']}</b>{detail}")
    await message.answer("<b>📜 Owner Action Logs</b>\n\n" + "\n".join(lines))
