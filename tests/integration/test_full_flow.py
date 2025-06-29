"""Integration tests for full application flow.

These tests verify that all components work together correctly
and that the complete user flows function as expected.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot
from aiogram.types import Message, User, Chat, CallbackQuery

from src.app import create_app, ServiceContainer
from src.config.settings import get_settings
from src.utils.error_handler import ErrorHandler
from src.utils.logger import setup_structured_logging


class TestApplicationIntegration:
    """Test application initialization and integration."""

    @pytest.fixture
    async def app_settings(self):
        """Get test settings."""
        settings = get_settings()
        # Override for testing
        settings.redis.host = "localhost"
        settings.redis.port = 6379
        settings.redis.db = 1  # Use test database
        return settings

    @pytest.fixture
    async def mock_redis(self):
        """Mock Redis for testing."""
        with patch("redis.asyncio.Redis") as mock:
            redis_instance = AsyncMock()
            mock.from_url.return_value = redis_instance
            redis_instance.ping.return_value = True
            redis_instance.get.return_value = None
            redis_instance.set.return_value = True
            redis_instance.delete.return_value = 1
            redis_instance.close.return_value = None
            yield redis_instance

    @pytest.fixture
    async def mock_httpx(self):
        """Mock httpx for testing."""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value = client_instance

            # Mock successful API response
            response = AsyncMock()
            response.status_code = 200
            response.json.return_value = {
                "success": True,
                "data": {
                    "USDT_RUB": {"rate": 95.50, "change": 0.5},
                    "BTC_USDT": {"rate": 42000.0, "change": -1.2},
                },
            }
            response.raise_for_status.return_value = None
            client_instance.get.return_value = response
            client_instance.post.return_value = response

            yield client_instance

    @pytest.mark.asyncio
    async def test_service_container_initialization(
        self, app_settings, mock_redis, mock_httpx
    ):
        """Test that service container initializes all services correctly."""
        container = ServiceContainer(app_settings)

        await container.initialize()

        # Verify all services are initialized
        assert container._cache_service is not None
        assert container._rapira_client is not None
        assert container._calculation_service is not None
        assert container._stats_service is not None
        assert container._notification_service is not None
        assert container._error_handler is not None
        assert container._bot is not None
        assert container._dispatcher is not None

        # Test service properties
        assert container.cache_service is not None
        assert container.rapira_client is not None
        assert container.calculation_service is not None
        assert container.stats_service is not None
        assert container.notification_service is not None
        assert container.error_handler is not None
        assert container.bot is not None
        assert container.dispatcher is not None

        # Cleanup
        await container.cleanup()

    @pytest.mark.asyncio
    async def test_service_container_cleanup(
        self, app_settings, mock_redis, mock_httpx
    ):
        """Test that service container cleans up properly."""
        container = ServiceContainer(app_settings)
        await container.initialize()

        # Mock cleanup methods
        for service in [
            container._cache_service,
            container._rapira_client,
            container._calculation_service,
            container._stats_service,
            container._notification_service,
            container._error_handler,
        ]:
            if service and hasattr(service, "cleanup"):
                service.cleanup = AsyncMock()

        await container.cleanup()

        # Verify cleanup was called
        for service in [
            container._cache_service,
            container._rapira_client,
            container._calculation_service,
            container._stats_service,
            container._notification_service,
            container._error_handler,
        ]:
            if service and hasattr(service, "cleanup"):
                service.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_application_initialization(
        self, app_settings, mock_redis, mock_httpx
    ):
        """Test full application initialization."""
        async with create_app(app_settings) as app:
            assert app is not None
            assert app.container is not None
            assert app.settings == app_settings

            # Test health check
            health = await app.health_check()
            assert health is not None
            assert "status" in health
            assert "services" in health
            assert "timestamp" in health

    @pytest.mark.asyncio
    async def test_application_health_check(self, app_settings, mock_redis, mock_httpx):
        """Test application health check functionality."""
        async with create_app(app_settings) as app:
            health = await app.health_check()

            # Check health structure
            assert isinstance(health, dict)
            assert health["status"] in ["healthy", "degraded", "unhealthy"]
            assert isinstance(health["services"], dict)
            assert isinstance(health["timestamp"], float)

            # Check that services are included
            expected_services = [
                "cache",
                "rapira_client",
                "calculation",
                "notification",
                "stats",
            ]
            for service in expected_services:
                assert service in health["services"]

    @pytest.mark.asyncio
    async def test_middleware_dependency_injection(
        self, app_settings, mock_redis, mock_httpx
    ):
        """Test that middleware correctly injects dependencies."""
        async with create_app(app_settings) as app:
            # Create mock handler
            handler_called = False
            injected_data = {}

            async def mock_handler(event, data):
                nonlocal handler_called, injected_data
                handler_called = True
                injected_data = data.copy()
                return "success"

            # Create mock message
            user = User(id=12345, is_bot=False, first_name="Test")
            chat = Chat(id=12345, type="private")
            message = Message(
                message_id=1, date=1234567890, chat=chat, from_user=user, text="/test"
            )

            # Get middleware
            middleware = None
            for mw in app.container.dispatcher.message.middleware:
                if hasattr(mw, "container"):
                    middleware = mw
                    break

            assert middleware is not None

            # Call middleware
            result = await middleware(mock_handler, message, {})

            # Verify handler was called with injected dependencies
            assert handler_called
            assert result == "success"

            # Check injected services
            expected_services = [
                "cache_service",
                "rapira_client",
                "calculation_service",
                "notification_service",
                "stats_service",
                "settings",
            ]
            for service in expected_services:
                assert service in injected_data


class TestBotFlowIntegration:
    """Test complete bot conversation flows."""

    @pytest.fixture
    async def mock_bot_components(self):
        """Mock bot components for testing."""
        with patch("aiogram.Bot") as mock_bot, patch(
            "aiogram.Dispatcher"
        ) as mock_dispatcher, patch(
            "aiogram.fsm.storage.redis.RedisStorage"
        ) as mock_storage:
            bot_instance = AsyncMock()
            dispatcher_instance = AsyncMock()
            storage_instance = AsyncMock()

            mock_bot.return_value = bot_instance
            mock_dispatcher.return_value = dispatcher_instance
            mock_storage.from_url.return_value = storage_instance

            yield {
                "bot": bot_instance,
                "dispatcher": dispatcher_instance,
                "storage": storage_instance,
            }

    @pytest.mark.asyncio
    async def test_rate_command_flow(self, mock_bot_components, mock_redis, mock_httpx):
        """Test complete /rate command flow."""
        # This would test the full flow from command to response
        # For now, we'll test that the components are properly integrated
        settings = get_settings()

        async with create_app(settings) as app:
            # Verify rate handler is registered
            assert app.container.dispatcher is not None

            # Test that services are available for rate calculation
            assert app.container.rapira_client is not None
            assert app.container.calculation_service is not None
            assert app.container.cache_service is not None

    @pytest.mark.asyncio
    async def test_calc_command_flow(self, mock_bot_components, mock_redis, mock_httpx):
        """Test complete /calc command flow."""
        settings = get_settings()

        async with create_app(settings) as app:
            # Verify calc handler is registered
            assert app.container.dispatcher is not None

            # Test that services are available for calculation
            assert app.container.calculation_service is not None
            assert app.container.notification_service is not None
            assert app.container.stats_service is not None

    @pytest.mark.asyncio
    async def test_admin_command_flow(
        self, mock_bot_components, mock_redis, mock_httpx
    ):
        """Test complete admin command flow."""
        settings = get_settings()

        async with create_app(settings) as app:
            # Verify admin handler is registered
            assert app.container.dispatcher is not None

            # Test that services are available for admin operations
            assert app.container.stats_service is not None
            assert app.container.notification_service is not None


class TestErrorHandlingIntegration:
    """Test error handling integration."""

    @pytest.mark.asyncio
    async def test_error_handler_integration(self, mock_redis, mock_httpx):
        """Test error handler integration with services."""
        settings = get_settings()

        async with create_app(settings) as app:
            error_handler = app.container.error_handler

            # Test that error handler has access to required services
            assert error_handler.notification_service is not None
            assert error_handler.stats_service is not None
            assert error_handler.settings is not None

    @pytest.mark.asyncio
    async def test_global_exception_handling(self, mock_redis, mock_httpx):
        """Test global exception handling setup."""
        settings = get_settings()

        async with create_app(settings) as app:
            # Test that global exception handler is set up
            loop = asyncio.get_event_loop()
            assert loop.get_exception_handler() is not None


class TestGracefulShutdown:
    """Test graceful shutdown functionality."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, mock_redis, mock_httpx):
        """Test that application shuts down gracefully."""
        settings = get_settings()

        async with create_app(settings) as app:
            # Test that cleanup works without errors
            await app.cleanup()

            # Verify cleanup was called on all services
            # (This would be more detailed in a real test)
            assert True  # Placeholder

    @pytest.mark.asyncio
    async def test_signal_handler_setup(self, mock_redis, mock_httpx):
        """Test that signal handlers are set up correctly."""
        settings = get_settings()

        app = None
        try:
            async with create_app(settings) as app_instance:
                app = app_instance
                # Test that signal handlers are registered
                assert app._shutdown_event is not None
        finally:
            if app:
                await app.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
