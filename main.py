#!/usr/bin/env python3
"""
Crypto Bot - Main Entry Point

Telegram bot for real-time currency exchange rates with Rapira API integration.
Production-ready implementation with comprehensive error handling and monitoring.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import after path setup
from app import create_app  # noqa: E402
from config.settings import get_settings  # noqa: E402
from utils.logger import setup_structured_logging, get_logger  # noqa: E402


async def main() -> int:
    """Main application entry point."""
    try:
        # Get settings first
        settings = get_settings()

        # Setup structured logging
        setup_structured_logging(settings)
        logger = get_logger(__name__)
        logger.info("🚀 Starting Crypto Bot...")

        # Log configuration
        logger.info(
            "📋 Configuration loaded",
            environment=settings.application.environment,
            debug=settings.application.debug,
            supported_pairs=len(settings.supported_pairs_list),
            admin_users=len(settings.telegram.admin_user_ids),
        )

        # Create and run application
        async with create_app(settings) as app:
            logger.info("✅ Application initialized successfully!")

            # Perform health check
            health = await app.health_check()
            if health["status"] != "healthy":
                logger.warning("⚠️ Health check failed", health_status=health)
            else:
                logger.info("✅ All systems healthy")

            # Run the bot
            await app.run_polling()

        return 0

    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
        return 0
    except Exception as e:
        logger.error("💥 Critical error occurred", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    # Ensure proper event loop for Windows
    if sys.platform.startswith("win"):
        policy = asyncio.WindowsProactorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)

    # Run the bot
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
