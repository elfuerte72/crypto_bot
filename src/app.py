"""Main application module for Crypto Bot.

This module provides the main application factory and service container
for dependency injection and lifecycle management.
"""

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, Dict, Optional

import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bot.handlers import admin_router, basic_router, calc_router, rate_router
from config.settings import Settings, get_settings
from services.cache_service import CacheService
from services.calculation_service import CalculationService
from services.notification_service import NotificationService
from services.rapira_client import RapiraApiClient
from services.stats_service import StatsService
from utils.error_handler import ErrorHandler
from utils.logger import get_logger


class ServiceContainer:
    """Dependency injection container for services."""

    def __init__(self, settings: Settings) -> None:
        """Initialize service container."""
        self.settings = settings
        self.logger = get_logger(__name__)

        # Core services
        self._cache_service: Optional[CacheService] = None
        self._rapira_client: Optional[RapiraApiClient] = None
        self._calculation_service: Optional[CalculationService] = None
        self._notification_service: Optional[NotificationService] = None
        self._stats_service: Optional[StatsService] = None
        self._error_handler: Optional[ErrorHandler] = None

        # Bot components
        self._bot: Optional[Bot] = None
        self._dispatcher: Optional[Dispatcher] = None
        self._storage: Optional[RedisStorage] = None

    async def initialize(self) -> None:
        """Initialize all services in correct order."""
        self.logger.info("🔧 Initializing services...")

        try:
            # Initialize core services first
            await self._initialize_cache_service()
            await self._initialize_rapira_client()
            await self._initialize_calculation_service()
            await self._initialize_stats_service()
            await self._initialize_notification_service()
            await self._initialize_error_handler()

            # Initialize bot components
            await self._initialize_bot_components()

            self.logger.info("✅ All services initialized successfully")

        except Exception as e:
            self.logger.error(f"💥 Service initialization failed: {e}")
            await self.cleanup()
            raise

    async def cleanup(self) -> None:
        """Cleanup all services."""
        self.logger.info("🧹 Cleaning up services...")

        # Cleanup in reverse order
        services = [
            ("Bot", self._bot),
            ("Error Handler", self._error_handler),
            ("Notification Service", self._notification_service),
            ("Stats Service", self._stats_service),
            ("Calculation Service", self._calculation_service),
            ("Rapira Client", self._rapira_client),
            ("Cache Service", self._cache_service),
        ]

        for name, service in services:
            if service and hasattr(service, "cleanup"):
                try:
                    await service.cleanup()
                    self.logger.debug(f"✅ {name} cleaned up")
                except Exception as e:
                    self.logger.warning(f"⚠️ {name} cleanup failed: {e}")

        # Close Redis storage
        if self._storage:
            try:
                await self._storage.close()
                self.logger.debug("✅ Redis storage closed")
            except Exception as e:
                self.logger.warning(f"⚠️ Redis storage cleanup failed: {e}")

    async def _initialize_cache_service(self) -> None:
        """Initialize cache service."""
        self._cache_service = CacheService.create(self.settings)
        await self._cache_service.initialize()
        self.logger.debug("✅ Cache service initialized")

    async def _initialize_rapira_client(self) -> None:
        """Initialize Rapira API client."""
        self._rapira_client = RapiraApiClient.create(self.settings)
        await self._rapira_client.initialize()
        self.logger.debug("✅ Rapira client initialized")

    async def _initialize_calculation_service(self) -> None:
        """Initialize calculation service."""
        self._calculation_service = CalculationService(self.settings)
        await self._calculation_service.initialize()
        self.logger.debug("✅ Calculation service initialized")

    async def _initialize_stats_service(self) -> None:
        """Initialize statistics service."""
        self._stats_service = StatsService(
            cache_service=self.cache_service, settings=self.settings
        )
        await self._stats_service.initialize()
        self.logger.debug("✅ Stats service initialized")

    async def _initialize_notification_service(self) -> None:
        """Initialize notification service."""
        # Create a temporary bot instance for notifications
        temp_bot = Bot(token=self.settings.telegram.token)

        self._notification_service = NotificationService(
            bot=temp_bot, settings=self.settings
        )
        await self._notification_service.initialize()
        self.logger.debug("✅ Notification service initialized")

    async def _initialize_error_handler(self) -> None:
        """Initialize error handler."""
        self._error_handler = ErrorHandler(
            notification_service=self.notification_service,
            stats_service=self.stats_service,
            settings=self.settings,
        )
        await self._error_handler.initialize()
        self.logger.debug("✅ Error handler initialized")

    async def _initialize_bot_components(self) -> None:
        """Initialize bot and dispatcher."""
        # Create Redis storage for FSM
        self._storage = RedisStorage.from_url(
            self.settings.redis.connection_url,
            key_builder=lambda chat_id, user_id: f"fsm:{chat_id}:{user_id}",
        )

        # Create bot and dispatcher
        self._bot = Bot(token=self.settings.telegram.token)
        self._dispatcher = Dispatcher(storage=self._storage)

        # Register routers
        self._dispatcher.include_router(basic_router)
        self._dispatcher.include_router(rate_router)
        self._dispatcher.include_router(calc_router)
        self._dispatcher.include_router(admin_router)

        # Setup middleware
        await self._setup_middleware()

        self.logger.debug("✅ Bot components initialized")

    async def _setup_middleware(self) -> None:
        """Setup middleware for dependency injection and error handling."""
        from aiogram import BaseMiddleware
        from aiogram.types import TelegramObject
        from typing import Callable, Dict, Any, Awaitable

        class DependencyInjectionMiddleware(BaseMiddleware):
            """Middleware for injecting services into handlers."""

            def __init__(self, container: "ServiceContainer"):
                self.container = container

            async def __call__(
                self,
                handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                event: TelegramObject,
                data: Dict[str, Any],
            ) -> Any:
                # Inject services into handler data
                data["cache_service"] = self.container.cache_service
                data["rapira_client"] = self.container.rapira_client
                data["calculation_service"] = self.container.calculation_service
                data["notification_service"] = self.container.notification_service
                data["stats_service"] = self.container.stats_service
                data["settings"] = self.container.settings

                return await handler(event, data)

        # Register middleware
        self._dispatcher.message.middleware(DependencyInjectionMiddleware(self))
        self._dispatcher.callback_query.middleware(DependencyInjectionMiddleware(self))

    # Properties for accessing services
    @property
    def cache_service(self) -> CacheService:
        """Get cache service."""
        if self._cache_service is None:
            raise RuntimeError("Cache service not initialized")
        return self._cache_service

    @property
    def rapira_client(self) -> RapiraApiClient:
        """Get Rapira API client."""
        if self._rapira_client is None:
            raise RuntimeError("Rapira client not initialized")
        return self._rapira_client

    @property
    def calculation_service(self) -> CalculationService:
        """Get calculation service."""
        if self._calculation_service is None:
            raise RuntimeError("Calculation service not initialized")
        return self._calculation_service

    @property
    def notification_service(self) -> NotificationService:
        """Get notification service."""
        if self._notification_service is None:
            raise RuntimeError("Notification service not initialized")
        return self._notification_service

    @property
    def stats_service(self) -> StatsService:
        """Get statistics service."""
        if self._stats_service is None:
            raise RuntimeError("Stats service not initialized")
        return self._stats_service

    @property
    def error_handler(self) -> ErrorHandler:
        """Get error handler."""
        if self._error_handler is None:
            raise RuntimeError("Error handler not initialized")
        return self._error_handler

    @property
    def bot(self) -> Bot:
        """Get bot instance."""
        if self._bot is None:
            raise RuntimeError("Bot not initialized")
        return self._bot

    @property
    def dispatcher(self) -> Dispatcher:
        """Get dispatcher instance."""
        if self._dispatcher is None:
            raise RuntimeError("Dispatcher not initialized")
        return self._dispatcher


class CryptoBotApplication:
    """Main application class."""

    def __init__(self, settings: Settings) -> None:
        """Initialize application."""
        self.settings = settings
        self.logger = get_logger(__name__)
        self.container = ServiceContainer(settings)
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize application."""
        self.logger.info("🚀 Initializing Crypto Bot Application...")

        # Setup signal handlers
        self._setup_signal_handlers()

        # Initialize service container
        await self.container.initialize()

        self.logger.info("✅ Application initialized successfully")

    async def run_polling(self) -> None:
        """Run bot in polling mode."""
        self.logger.info("🔄 Starting bot polling...")

        try:
            # Start polling with graceful shutdown
            await self.container.dispatcher.start_polling(
                self.container.bot,
                allowed_updates=["message", "callback_query"],
                handle_as_tasks=True,
            )
        except asyncio.CancelledError:
            self.logger.info("🛑 Polling cancelled")
        except Exception as e:
            self.logger.error(f"💥 Polling error: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Perform application health check."""
        health = {
            "status": "healthy",
            "services": {},
            "timestamp": asyncio.get_event_loop().time(),
        }

        # Check each service
        services = [
            ("cache", self.container._cache_service),
            ("rapira_client", self.container._rapira_client),
            ("calculation", self.container._calculation_service),
            ("notification", self.container._notification_service),
            ("stats", self.container._stats_service),
        ]

        for name, service in services:
            if service is None:
                health["services"][name] = {"status": "not_initialized"}
                health["status"] = "degraded"
            elif hasattr(service, "health_check"):
                try:
                    service_health = await service.health_check()
                    health["services"][name] = service_health
                    if service_health.get("status") != "healthy":
                        health["status"] = "degraded"
                except Exception as e:
                    health["services"][name] = {"status": "error", "error": str(e)}
                    health["status"] = "unhealthy"
            else:
                health["services"][name] = {"status": "healthy"}

        return health

    async def cleanup(self) -> None:
        """Cleanup application."""
        self.logger.info("🧹 Shutting down application...")
        await self.container.cleanup()
        self.logger.info("👋 Application shutdown complete")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            self.logger.info(f"📡 Received signal {signum}, initiating shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def __aenter__(self) -> "CryptoBotApplication":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.cleanup()


@asynccontextmanager
async def create_app(
    settings: Optional[Settings] = None,
) -> AsyncContextManager[CryptoBotApplication]:
    """Create and initialize application.

    Args:
        settings: Application settings. If None, will be loaded from environment.

    Returns:
        Initialized application instance.
    """
    if settings is None:
        settings = get_settings()

    app = CryptoBotApplication(settings)

    try:
        await app.initialize()
        yield app
    finally:
        await app.cleanup()
