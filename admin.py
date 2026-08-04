from aiogram import Bot
from aiogram.types import Chat, User
from config import OWNER_ID


async def is_admin(bot: Bot, chat: Chat, user: User) -> bool:
    """Check karta hai ki user group admin/creator hai ya bot owner hai."""
    if user.id == OWNER_ID:
        return True
    if chat.type == "private":
        return True
    try:
        member = await bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False
