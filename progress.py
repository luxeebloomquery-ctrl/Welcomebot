import asyncio
from aiogram import Bot


def render_bar(percent: int, length: int = 10) -> str:
    """0-100 percent se ek visual progress bar banata hai: ██████░░░░ 60%"""
    percent = max(0, min(100, percent))
    filled = round((percent / 100) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {percent}%"


class ProgressMessage:
    """
    Ek editable message jo baar baar update hoti hai (naya message nahi bhejta).
    Debounce built-in hai taaki Telegram rate-limit na kare.
    Usage:
        p = ProgressMessage(bot, chat_id)
        await p.start("Processing...")
        await p.update(30, "Uploading media...")
        await p.finish("✅ Done!")
    """

    def __init__(self, bot: Bot, chat_id: int, min_edit_gap: float = 1.2):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id: int | None = None
        self._last_edit = 0.0
        self._min_gap = min_edit_gap
        self._last_percent = -1

    async def start(self, label: str, percent: int = 0):
        text = f"{label}\n{render_bar(percent)}"
        msg = await self.bot.send_message(self.chat_id, text)
        self.message_id = msg.message_id
        self._last_percent = percent
        self._last_edit = asyncio.get_event_loop().time()
        return self

    async def update(self, percent: int, label: str, force: bool = False):
        """Debounced update — same percent ya bahut jaldi call hone par skip karta hai."""
        if self.message_id is None:
            await self.start(label, percent)
            return

        now = asyncio.get_event_loop().time()
        if not force:
            if percent == self._last_percent:
                return
            if now - self._last_edit < self._min_gap and percent < 100:
                return

        text = f"{label}\n{render_bar(percent)}"
        try:
            await self.bot.edit_message_text(text, chat_id=self.chat_id, message_id=self.message_id)
            self._last_percent = percent
            self._last_edit = now
        except Exception:
            pass  # "message not modified" jaisi harmless errors ignore

    async def finish(self, final_text: str):
        if self.message_id is None:
            await self.bot.send_message(self.chat_id, final_text)
            return
        try:
            await self.bot.edit_message_text(final_text, chat_id=self.chat_id, message_id=self.message_id)
        except Exception:
            await self.bot.send_message(self.chat_id, final_text)
