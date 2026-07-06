# app/main.py
import logging
import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from aiogram import types
from app.config import settings
from app.bot.bot import bot, dp
from app.bot.handlers import router as bot_router

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sentry initialization
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.2,
    )

app = FastAPI(title="Resume Bot API", version="1.0.0")

# Register bot handlers to dispatcher
dp.include_router(bot_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Webhook endpoint for Telegram updates."""
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Error processing webhook update")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )

@app.on_event("startup")
async def on_startup():
    logger.info("Starting up server...")
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Cannot start API server.")
        raise ValueError("BOT_TOKEN is missing!")
    if settings.WEBHOOK_URL:
        webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}{settings.WEBHOOK_PATH}"
        logger.info(f"Setting Telegram Webhook to {webhook_url}")
        await bot.set_webhook(url=webhook_url)
    else:
        logger.info("No WEBHOOK_URL set. Bot will need to run in polling mode for local development.")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down server...")
    # Clean up webhook
    if settings.WEBHOOK_URL:
        await bot.delete_webhook()
    await bot.session.close()
