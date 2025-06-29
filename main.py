#!/usr/bin/env python3
"""
Crypto Bot - Main Entry Point

Telegram bot for real-time currency exchange rates with Rapira API integration.
Production-ready implementation with comprehensive error handling and monitoring.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import after path setup
from config.settings import get_settings  # noqa: E402
from bot.handlers import (
    basic_router,
    rate_router,
    calc_router,
    admin_router,
)  # noqa: E402
from services.cache_service import CacheServiceFactory  # noqa: E402
from services.stats_service import StatsServiceFactory  # noqa: E402
from bot.handlers.admin_handlers import get_admin_service  # noqa: E402


# Global variables for graceful shutdown
bot: Bot | None = None
dp: Dispatcher | None = None


async def setup_bot_commands(bot: Bot) -> None:
    """Setup bot commands for better UX."""
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="❓ Помощь по командам"),
        BotCommand(command="rate", description="💱 Посмотреть курс валют"),
        BotCommand(command="calc", description="🧮 Рассчитать сумму обмена"),
        BotCommand(command="set_markup", description="⚙️ Настроить наценку (админ)"),
        BotCommand(command="set_manager", description="👥 Назначить менеджера (админ)"),
        BotCommand(command="stats", description="📊 Показать статистику (админ)"),
    ]

    await bot.set_my_commands(commands)
    logging.info("✅ Bot commands configured successfully")


async def setup_logging() -> None:
    """Configure application logging."""
    settings = get_settings()

    # Determine log format based on settings
    if settings.logging.format.lower() == "json":
        log_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Configure aiogram logging
    aiogram_logger = logging.getLogger("aiogram")
    if settings.application.debug:
        aiogram_logger.setLevel(logging.INFO)
    else:
        aiogram_logger.setLevel(logging.WARNING)

    logging.info("✅ Logging configured successfully")


async def create_bot() -> Bot:
    """Create and configure bot instance."""
    settings = get_settings()

    # Create bot with default properties
    bot = Bot(
        token=settings.telegram.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    # Validate bot token
    try:
        bot_info = await bot.get_me()
        username = bot_info.username
        first_name = bot_info.first_name
        logging.info(f"✅ Bot authenticated: @{username} ({first_name})")
    except Exception as e:
        logging.error(f"❌ Bot authentication failed: {e}")
        raise

    return bot


async def create_dispatcher() -> Dispatcher:
    """Create and configure dispatcher with all routers."""
    settings = get_settings()

    # Create dispatcher
    dp = Dispatcher()

    # Create cache service for statistics
    try:
        cache_service = CacheServiceFactory.create_cache_service(settings)
        await cache_service.initialize()
        logging.info("✅ Cache service initialized")

        # Create statistics service
        stats_service = StatsServiceFactory.create_stats_service(
            settings, cache_service
        )
        await stats_service.initialize()
        logging.info("✅ Statistics service initialized")

        # Initialize admin service with statistics
        admin_service = get_admin_service(settings, stats_service)
        logging.info("✅ Admin service initialized with statistics")

    except Exception as e:
        logging.warning(f"⚠️ Failed to initialize statistics service: {e}")
        logging.info("📊 Statistics features will be disabled")

    # Include routers
    dp.include_router(basic_router)
    logging.info("✅ Basic handlers router registered")
    dp.include_router(rate_router)
    logging.info("✅ Rate handler router registered")
    dp.include_router(calc_router)
    logging.info("✅ Calc handler router registered")
    dp.include_router(admin_router)
    logging.info("✅ Admin handler router registered")

    # Add global data to dispatcher
    dp["settings"] = settings

    logging.info("✅ Dispatcher configured successfully")
    return dp


async def on_startup() -> None:
    """Startup hook for initialization."""
    logging.info("🚀 Starting Crypto Bot...")

    # Setup bot commands
    if bot:
        await setup_bot_commands(bot)

    # Log configuration
    settings = get_settings()
    logging.info(f"📋 Environment: {settings.application.environment}")
    logging.info(f"🔧 Debug mode: {settings.application.debug}")
    pairs_count = len(settings.supported_pairs_list)
    logging.info(f"💱 Supported pairs: {pairs_count}")
    admin_count = len(settings.telegram.admin_user_ids)
    logging.info(f"👥 Admin users: {admin_count}")

    logging.info("✅ Bot startup completed successfully!")


async def on_shutdown() -> None:
    """Shutdown hook for cleanup."""
    logging.info("🛑 Shutting down Crypto Bot...")

    # Close bot session
    if bot:
        await bot.session.close()
        logging.info("✅ Bot session closed")

    logging.info("✅ Shutdown completed successfully!")


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum: int, frame: Any) -> None:
        msg = f"📡 Received signal {signum}, initiating graceful shutdown..."
        logging.info(msg)
        if dp:
            dp.stop_polling()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Main application entry point."""
    global bot, dp

    try:
        # Setup logging first
        await setup_logging()

        # Setup signal handlers
        setup_signal_handlers()

        # Create bot and dispatcher
        bot = await create_bot()
        dp = await create_dispatcher()

        # Run startup hook
        await on_startup()

        # Start polling
        logging.info("🔄 Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )

    except KeyboardInterrupt:
        logging.info("👋 Bot stopped by user")
    except Exception as e:
        logging.error(f"💥 Critical error: {e}", exc_info=True)
        return 1
    finally:
        # Run shutdown hook
        await on_shutdown()

    return 0


if __name__ == "__main__":
    # Ensure proper event loop for Windows
    if sys.platform.startswith("win"):
        policy = asyncio.WindowsProactorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)

    # Run the bot
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
