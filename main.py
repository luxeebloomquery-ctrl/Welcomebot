import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import LinkPreviewOptions
from config import BOT_TOKEN
import database as db
from handlers.album import router as album_router
from handlers.backup import router as backup_router
from handlers.builder import router as builder_router
from handlers.card import router as card_router
from handlers.editor import router as editor_router
from handlers.goodbye import router as goodbye_router
#from handlers.health import router as health_router
from handlers.owner import router as owner_router
from handlers.ownermgmt import router as ownermgmt_router
from handlers.scheduler import router as scheduler_router
from handlers.templates import router as templates_router
from handlers.welcome import router as welcome_router
from utils.scheduler import scheduler_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await db.init_db()

    bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview=False,
    ),
    )
    
    
        
        
    
    dp = Dispatcher()

    dp.include_router(album_router)
    dp.include_router(owner_router)
    dp.include_router(ownermgmt_router)
    dp.include_router(templates_router)
    dp.include_router(editor_router)
    dp.include_router(card_router)
    dp.include_router(backup_router)
    dp.include_router(scheduler_router)
    #dp.include_router(health_router)
    dp.include_router(builder_router)
    dp.include_router(goodbye_router)
    dp.include_router(welcome_router)

    logger.info("Bot start ho raha hai...")
    scheduler_task = asyncio.create_task(scheduler_loop(bot))
    try:
        await dp.start_polling(bot, allowed_updates=["message", "chat_member", "my_chat_member", "callback_query"])
    finally:
        scheduler_task.cancel()
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
