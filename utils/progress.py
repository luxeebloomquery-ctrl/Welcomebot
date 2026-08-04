import asyncio
from aiogram import Bot
from aiogram.types import LinkPreviewOptions


class ProgressMessage:
    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.msg = None

    async def start(self, text: str = "Processing..."):
        try:
            self.msg = await self.bot.send_message(
                self.chat_id,
                text,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception as e:
            print(f"Progress start error: {e}")

    async def update(self, text: str):
        if not self.msg:
            return
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.msg.message_id,
                text=text,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception:
            pass

    async def finish(self, text: str = None):
        if not self.msg:
            return
        try:
            if text:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.msg.message_id,
                    text=text,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            else:
                await self.bot.delete_message(self.chat_id, self.msg.message_id)
        except Exception:
            pass
            
