"""Tests for error handler functionality."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, CallbackQuery, User, Chat

from src.utils.error_handler import (
    ErrorHandler,
    BotError,
    TelegramError,
    TimeoutError,
    ConnectionError,
    ValidationError,
    ErrorType,
    ErrorSeverity,
    handle_errors,
)
from src.config.settings import Settings
from src.services.notification_service import NotificationService
from src.services.stats_service import StatsService


class TestBotError:
    """Test BotError class functionality."""

    def test_bot_error_initialization(self):
        """Test BotError initialization with default values."""
        error = BotError("Test error message")

        assert str(error) == "Test error message"
        assert error.error_type == ErrorType.UNKNOWN
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.correlation_id is not None
        assert len(error.correlation_id) == 8
        assert error.context == {}
        assert isinstance(error.timestamp, datetime)

    def test_bot_error_with_custom_values(self):
        """Test BotError initialization with custom values."""
        context = {"user_id": 12345, "action": "test"}
        error = BotError(
            "Custom error",
            error_type=ErrorType.VALIDATION,
            severity=ErrorSeverity.HIGH,
            user_message="Custom user message",
            correlation_id="test123",
            context=context,
        )

        assert str(error) == "Custom error"
        assert error.error_type == ErrorType.VALIDATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.user_message == "Custom user message"
        assert error.correlation_id == "test123"
        assert error.context == context

    def test_default_user_messages(self):
        """Test default user messages for different error types."""
        test_cases = [
            (ErrorType.TELEGRAM_API, "🤖 Произошла ошибка Telegram API"),
            (ErrorType.TIMEOUT, "⏰ Превышено время ожидания"),
            (ErrorType.CONNECTION, "🌐 Проблемы с подключением"),
            (ErrorType.VALIDATION, "❌ Некорректные данные"),
            (ErrorType.UNKNOWN, "❓ Произошла неизвестная ошибка"),
        ]

        for error_type, expected_message in test_cases:
            error = BotError("Test", error_type=error_type)
            assert expected_message in error.user_message

    def test_to_dict(self):
        """Test error serialization to dictionary."""
        context = {"test": "value"}
        error = BotError(
            "Test error",
            error_type=ErrorType.VALIDATION,
            severity=ErrorSeverity.HIGH,
            correlation_id="test123",
            context=context,
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Test error"
        assert error_dict["error_type"] == "validation"
        assert error_dict["severity"] == "high"
        assert error_dict["correlation_id"] == "test123"
        assert error_dict["context"] == context
        assert "timestamp" in error_dict


class TestSpecificErrors:
    """Test specific error types."""

    def test_telegram_error(self):
        """Test TelegramError initialization."""
        error = TelegramError("Telegram API failed")

        assert error.error_type == ErrorType.TELEGRAM_API
        assert "Telegram API" in error.user_message

    def test_timeout_error(self):
        """Test TimeoutError initialization."""
        error = TimeoutError("Request timed out")

        assert error.error_type == ErrorType.TIMEOUT
        assert "время ожидания" in error.user_message

    def test_connection_error(self):
        """Test ConnectionError initialization."""
        error = ConnectionError("Connection failed")

        assert error.error_type == ErrorType.CONNECTION
        assert "подключением" in error.user_message

    def test_validation_error(self):
        """Test ValidationError initialization."""
        error = ValidationError("Invalid input")

        assert error.error_type == ErrorType.VALIDATION
        assert error.severity == ErrorSeverity.LOW
        assert "данные" in error.user_message


class TestErrorHandler:
    """Test ErrorHandler class functionality."""

    @pytest.fixture
    def mock_notification_service(self):
        """Mock notification service."""
        service = AsyncMock(spec=NotificationService)
        service.send_admin_notification = AsyncMock()
        return service

    @pytest.fixture
    def mock_stats_service(self):
        """Mock stats service."""
        service = AsyncMock(spec=StatsService)
        service.track_error = AsyncMock()
        return service

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        # Use real settings structure but with test values
        from src.config.models import TelegramConfig, ApplicationConfig, LoggingConfig

        settings = MagicMock()
        settings.telegram = TelegramConfig(
            token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789",
            admin_user_ids=[12345, 67890],
        )
        settings.application = ApplicationConfig(environment="development", debug=True)
        settings.logging = LoggingConfig(level="INFO", format="json")
        return settings

    @pytest.fixture
    async def error_handler(
        self, mock_notification_service, mock_stats_service, mock_settings
    ):
        """Create error handler instance."""
        handler = ErrorHandler(
            notification_service=mock_notification_service,
            stats_service=mock_stats_service,
            settings=mock_settings,
        )
        await handler.initialize()
        return handler

    @pytest.mark.asyncio
    async def test_error_handler_initialization(
        self, mock_notification_service, mock_stats_service, mock_settings
    ):
        """Test error handler initialization."""
        handler = ErrorHandler(
            notification_service=mock_notification_service,
            stats_service=mock_stats_service,
            settings=mock_settings,
        )

        await handler.initialize()

        assert handler.notification_service == mock_notification_service
        assert handler.stats_service == mock_stats_service
        assert handler.settings == mock_settings

    @pytest.mark.asyncio
    async def test_convert_to_bot_error(self, error_handler):
        """Test conversion of standard exceptions to BotError."""
        # Test TelegramAPIError conversion
        telegram_error = TelegramAPIError("API Error")
        bot_error = error_handler._convert_to_bot_error(telegram_error)
        assert isinstance(bot_error, TelegramError)
        assert bot_error.error_type == ErrorType.TELEGRAM_API

        # Test asyncio.TimeoutError conversion
        timeout_error = asyncio.TimeoutError("Timeout")
        bot_error = error_handler._convert_to_bot_error(timeout_error)
        assert isinstance(bot_error, TimeoutError)
        assert bot_error.error_type == ErrorType.TIMEOUT

        # Test ValueError conversion
        value_error = ValueError("Invalid value")
        bot_error = error_handler._convert_to_bot_error(value_error)
        assert isinstance(bot_error, ValidationError)
        assert bot_error.error_type == ErrorType.VALIDATION

        # Test generic exception conversion
        generic_error = RuntimeError("Runtime error")
        bot_error = error_handler._convert_to_bot_error(generic_error)
        assert isinstance(bot_error, BotError)
        assert bot_error.error_type == ErrorType.UNKNOWN

    def test_extract_event_context_message(self, error_handler):
        """Test context extraction from Message event."""
        user = User(id=12345, is_bot=False, first_name="Test", username="testuser")
        chat = Chat(id=67890, type="private")
        message = Message(
            message_id=1,
            date=1234567890,
            chat=chat,
            from_user=user,
            text="/test command",
        )

        context = error_handler._extract_event_context(message)

        assert context["user_id"] == 12345
        assert context["username"] == "testuser"
        assert context["chat_id"] == 67890
        assert context["chat_type"] == "private"
        assert context["message_id"] == 1
        assert context["text"] == "/test command"

    def test_extract_event_context_callback(self, error_handler):
        """Test context extraction from CallbackQuery event."""
        user = User(id=12345, is_bot=False, first_name="Test")
        chat = Chat(id=67890, type="private")
        message = Message(message_id=1, date=1234567890, chat=chat)
        callback = CallbackQuery(
            id="callback123", from_user=user, data="test_callback_data", message=message
        )

        context = error_handler._extract_event_context(callback)

        assert context["user_id"] == 12345
        assert context["callback_data"] == "test_callback_data"
        assert context["message_id"] == 1

    @pytest.mark.asyncio
    async def test_track_error_stats(self, error_handler):
        """Test error statistics tracking."""
        error = BotError(
            "Test error",
            error_type=ErrorType.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            correlation_id="test123",
        )

        await error_handler._track_error_stats(error)

        error_handler.stats_service.track_error.assert_called_once_with(
            error_type="validation",
            severity="medium",
            correlation_id="test123",
            context={},
        )

    @pytest.mark.asyncio
    async def test_send_admin_notification(self, error_handler):
        """Test admin notification sending."""
        error = BotError(
            "Critical error",
            error_type=ErrorType.CONNECTION,
            severity=ErrorSeverity.CRITICAL,
            correlation_id="crit123",
        )

        await error_handler._send_admin_notification(error)

        # Should send to all admin users
        assert (
            error_handler.notification_service.send_admin_notification.call_count == 2
        )

        # Check calls
        calls = (
            error_handler.notification_service.send_admin_notification.call_args_list
        )
        admin_ids = [call[1]["admin_id"] for call in calls]
        assert 12345 in admin_ids
        assert 67890 in admin_ids

    @pytest.mark.asyncio
    async def test_send_user_error_message_to_message(self, error_handler):
        """Test sending error message to user via Message."""
        user = User(id=12345, is_bot=False, first_name="Test")
        chat = Chat(id=67890, type="private")
        message = AsyncMock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.answer = AsyncMock()

        error = BotError("Test error", correlation_id="test123")

        await error_handler._send_user_error_message(message, error)

        message.answer.assert_called_once()
        call_args = message.answer.call_args
        assert "test123" in call_args[0][0]  # Correlation ID in message
        assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_send_user_error_message_to_callback(self, error_handler):
        """Test sending error message to user via CallbackQuery."""
        user = User(id=12345, is_bot=False, first_name="Test")
        chat = Chat(id=67890, type="private")
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()

        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = user
        callback.message = message
        callback.answer = AsyncMock()

        error = BotError("Test error", correlation_id="test123")

        await error_handler._send_user_error_message(callback, error)

        callback.answer.assert_called_once()
        message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_complete_flow(self, error_handler):
        """Test complete error handling flow."""
        user = User(id=12345, is_bot=False, first_name="Test")
        chat = Chat(id=67890, type="private")
        message = AsyncMock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.message_id = 1
        message.text = "/test"
        message.answer = AsyncMock()

        # Create high severity error to trigger admin notification
        error = BotError(
            "High severity error",
            error_type=ErrorType.CONNECTION,
            severity=ErrorSeverity.HIGH,
            correlation_id="high123",
        )

        correlation_id = await error_handler.handle_error(error, message)

        # Verify correlation ID returned
        assert correlation_id == "high123"

        # Verify stats tracking called
        error_handler.stats_service.track_error.assert_called_once()

        # Verify admin notification sent (high severity)
        assert (
            error_handler.notification_service.send_admin_notification.call_count == 2
        )

        # Verify user message sent
        message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_standard_exception(self, error_handler):
        """Test handling of standard Python exceptions."""
        exception = ValueError("Invalid input value")

        correlation_id = await error_handler.handle_error(exception)

        # Should convert to BotError and handle
        assert correlation_id is not None
        assert len(correlation_id) == 8

        # Should track as validation error
        error_handler.stats_service.track_error.assert_called_once()
        call_args = error_handler.stats_service.track_error.call_args[1]
        assert call_args["error_type"] == "validation"

    @pytest.mark.asyncio
    async def test_handle_command_error(self, error_handler):
        """Test command-specific error handling."""
        user = User(id=12345, is_bot=False, first_name="Test")
        chat = Chat(id=67890, type="private")
        message = AsyncMock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.answer = AsyncMock()

        error = RuntimeError("Command failed")

        correlation_id = await error_handler.handle_command_error(
            error, message, "/rate"
        )

        # Should include command in context
        assert correlation_id is not None
        error_handler.stats_service.track_error.assert_called_once()
        call_args = error_handler.stats_service.track_error.call_args[1]
        assert call_args["context"]["command"] == "/rate"

    @pytest.mark.asyncio
    async def test_handle_callback_error(self, error_handler):
        """Test callback-specific error handling."""
        user = User(id=12345, is_bot=False, first_name="Test")
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = user
        callback.answer = AsyncMock()

        error = RuntimeError("Callback failed")

        correlation_id = await error_handler.handle_callback_error(
            error, callback, "rate_USDT_RUB"
        )

        # Should include callback data in context
        assert correlation_id is not None
        error_handler.stats_service.track_error.assert_called_once()
        call_args = error_handler.stats_service.track_error.call_args[1]
        assert call_args["context"]["callback_data"] == "rate_USDT_RUB"


class TestErrorDecorator:
    """Test error handling decorator."""

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self):
        """Test decorator with successful function execution."""

        @handle_errors(ErrorType.BUSINESS_LOGIC, ErrorSeverity.HIGH)
        async def test_function():
            return "success"

        result = await test_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_with_exception(self):
        """Test decorator with exception handling."""
        # Mock global error handler
        mock_handler = AsyncMock()
        with patch(
            "src.utils.error_handler.get_error_handler", return_value=mock_handler
        ):

            @handle_errors(
                ErrorType.BUSINESS_LOGIC, ErrorSeverity.HIGH, "Custom error message"
            )
            async def test_function():
                raise ValueError("Test error")

            with pytest.raises(ValueError):
                await test_function()

            # Verify error handler was called
            mock_handler.handle_error.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
