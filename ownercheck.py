import database as db


async def is_owner(user_id: int) -> bool:
    """DB ke owners table mein check karta hai (multi-owner support)."""
    return await db.is_owner(user_id)
