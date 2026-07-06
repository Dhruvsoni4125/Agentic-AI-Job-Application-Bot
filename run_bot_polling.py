import asyncio
import logging
from app.bot.bot import bot, dp
from app.bot.handlers import router as bot_router
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

async def main():
    # Include handlers
    dp.include_router(bot_router)
    
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Please configure it in your .env file.")
        return
        
    logger.info("De-registering any active webhooks...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Starting Telegram Bot in long-polling mode (local testing)...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
