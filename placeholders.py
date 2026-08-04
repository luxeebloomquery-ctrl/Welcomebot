from html import escape
from aiogram.types import User, Chat


def build_placeholders(user: User, chat: Chat, member_count: int) -> dict:
    """User, chat aur member count se saare Rose-style placeholders banata hai."""
    first = escape(user.first_name or "")
    last = escape(user.last_name or "")
    fullname = escape(f"{user.first_name or ''} {user.last_name or ''}".strip())
    username = f"@{user.username}" if user.username else first
    mention = f'<a href="tg://user?id={user.id}">{first}</a>'
    chatname = escape(chat.title or chat.first_name or "this chat")

    return {
        "first": first,
        "last": last,
        "fullname": fullname,
        "username": username,
        "mention": mention,
        "id": str(user.id),
        "chatname": chatname,
        "count": str(member_count),
    }


def apply_placeholders(text: str, user: User, chat: Chat, member_count: int) -> str:
    """Text ke andar {first}, {mention} jaise placeholders ko actual values se replace karta hai."""
    values = build_placeholders(user, chat, member_count)
    result = text
    for key, val in values.items():
        result = result.replace("{" + key + "}", val)
    return result
