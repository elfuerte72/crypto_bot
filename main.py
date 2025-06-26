#!/usr/bin/env python3
"""
Crypto Bot - Main Entry Point

Telegram bot for real-time currency exchange rates with Rapira API integration.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.settings import settings
from src.bot.main import create_bot, setup_handlers
from src.services import ServiceManager


async def main() -> None:
    """Main application entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("crypto_bot.log")
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Crypto Bot...")
    
    try:
        # Initialize services
        service_manager = ServiceManager()
        await service_manager.initialize()
        
        # Create and configure bot
        bot = create_bot(settings.BOT_TOKEN)
        dp = setup_handlers(service_manager)
        
        # Start polling
        logger.info("Bot is starting...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
    finally:
        # Cleanup
        if 'service_manager' in locals():
            await service_manager.cleanup()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)