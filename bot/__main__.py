import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.db import init_db
from bot.handlers import setup_routers

# Configuration
ENV = os.getenv("ENV", "dev").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(
    token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
)
dp = Dispatcher()


async def on_startup(bot: Bot) -> None:
    """Startup hook - runs when bot starts."""
    # Clear old webhooks and pending updates
    await bot.delete_webhook(drop_pending_updates=True)

    # Get bot info
    me = await bot.get_me()
    logger.info(
        f"Bot started: ENV={ENV}, bot_id={me.id}, "
        f"username=@{me.username}, name={me.first_name}"
    )

    # Set bot commands menu
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Начать тестирование"),
            BotCommand(command="feedback", description="Оставить отзыв"),
        ],
        scope=BotCommandScopeDefault(),
    )
    logger.info("Bot commands menu updated")


async def main() -> None:
    """Main entry point."""
    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Register startup hook
    dp.startup.register(on_startup)

    # Setup routers
    router = setup_routers()
    dp.include_router(router)
    logger.info("Routers registered")

    # Start polling
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
