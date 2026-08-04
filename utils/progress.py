cat << 'EOF' > utils/progress.py
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

    async def update(self, *args):
        if not self.msg:
            return
        # Supports both update("text") and update(50, "text")
        text = args[-1] if len(args) > 0 and isinstance(args[-1], str) else str(args)
        if len(args) == 2 and isinstance(args[0], (int, float)):
            text = f"[{args[0]}%] {text}"
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
EOF

