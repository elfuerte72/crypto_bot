"""Centralized error handling system for the crypto bot.

This module provides comprehensive error handling with correlation IDs,
user-friendly messages, and admin notifications.
"""

import asyncio
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Type, Union

import structlog
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, CallbackQuery

from config.settings import Settings
from services.notification_service import NotificationService
from services.stats_service import StatsService


class ErrorType(Enum):
    """Types of errors that can occur."""

    TELEGRAM_API = "telegram_api"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_API = "external_api"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BotError(Exception):
    """Base exception for bot errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        user_message: Optional[str] = None,
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize bot error.

        Args:
            message: Technical error message
            error_type: Type of error
            severity: Error severity level
            user_message: User-friendly error message
            correlation_id: Unique correlation ID for tracking
            context: Additional context information
        """
        super().__init__(message)
        self.error_type = error_type
        self.severity = severity
        self.user_message = user_message or self._get_default_user_message()
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)

    def _get_default_user_message(self) -> str:
        """Get default user-friendly message based on error type."""
        messages = {
            ErrorType.TELEGRAM_API: "🤖 Произошла ошибка Telegram API. Попробуйте позже.",
            ErrorType.TIMEOUT: "⏰ Превышено время ожидания. Попробуйте еще раз.",
            ErrorType.CONNECTION: "🌐 Проблемы с подключением. Проверьте интернет-соединение.",
            ErrorType.VALIDATION: "❌ Некорректные данные. Проверьте введенную информацию.",
            ErrorType.RATE_LIMIT: "🚦 Слишком много запросов. Подождите немного.",
            ErrorType.AUTHENTICATION: "🔐 Ошибка аутентификации. Обратитесь к администратору.",
            ErrorType.PERMISSION: "🚫 Недостаточно прав для выполнения операции.",
            ErrorType.BUSINESS_LOGIC: "💼 Ошибка в бизнес-логике. Обратитесь к поддержке.",
            ErrorType.EXTERNAL_API: "🔌 Ошибка внешнего API. Попробуйте позже.",
            ErrorType.UNKNOWN: "❓ Произошла неизвестная ошибка. Обратитесь к поддержке.",
        }
        return messages.get(self.error_type, messages[ErrorType.UNKNOWN])

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "message": str(self),
            "error_type": self.error_type.value,
            "severity": self.severity.value,
            "user_message": self.user_message,
            "correlation_id": self.correlation_id,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "traceback": traceback.format_exc()
            if hasattr(self, "__traceback__")
            else None,
        }


class TelegramError(BotError):
    """Telegram API related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.TELEGRAM_API, **kwargs)


class TimeoutError(BotError):
    """Timeout related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.TIMEOUT, **kwargs)


class ConnectionError(BotError):
    """Connection related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.CONNECTION, **kwargs)


class ValidationError(BotError):
    """Validation related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=ErrorType.VALIDATION,
            severity=ErrorSeverity.LOW,
            **kwargs,
        )


class ErrorHandler:
    """Centralized error handler for the bot."""

    def __init__(
        self,
        notification_service: Optional[NotificationService] = None,
        stats_service: Optional[StatsService] = None,
        settings: Optional[Settings] = None,
    ):
        """Initialize error handler.

        Args:
            notification_service: Service for sending notifications
            stats_service: Service for tracking statistics
            settings: Application settings
        """
        self.notification_service = notification_service
        self.stats_service = stats_service
        self.settings = settings
        self.logger = structlog.get_logger(__name__)

        # Setup global exception handler
        self._setup_global_exception_handler()

    async def initialize(self) -> None:
        """Initialize error handler."""
        self.logger.info("🔧 Error handler initialized")

    async def cleanup(self) -> None:
        """Cleanup error handler."""
        self.logger.debug("🧹 Error handler cleaned up")

    def _setup_global_exception_handler(self) -> None:
        """Setup global exception handler for asyncio."""

        def exception_handler(
            loop: asyncio.AbstractEventLoop, context: Dict[str, Any]
        ) -> None:
            exception = context.get("exception")
            if exception:
                asyncio.create_task(self._handle_global_exception(exception, context))

        try:
            loop = asyncio.get_event_loop()
            loop.set_exception_handler(exception_handler)
        except RuntimeError:
            # No event loop running yet
            pass

    async def _handle_global_exception(
        self, exception: Exception, context: Dict[str, Any]
    ) -> None:
        """Handle global asyncio exceptions."""
        error = BotError(
            message=f"Global exception: {exception}",
            error_type=ErrorType.UNKNOWN,
            severity=ErrorSeverity.HIGH,
            context=context,
        )
        await self.handle_error(error)

    async def handle_error(
        self,
        error: Union[Exception, BotError],
        event: Optional[Union[Message, CallbackQuery]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Handle an error with comprehensive logging and notifications.

        Args:
            error: The error to handle
            event: Telegram event that caused the error
            context: Additional context information

        Returns:
            Correlation ID for tracking
        """
        # Convert to BotError if needed
        if not isinstance(error, BotError):
            bot_error = self._convert_to_bot_error(error)
        else:
            bot_error = error

        # Add context from event
        if event:
            bot_error.context.update(self._extract_event_context(event))

        if context:
            bot_error.context.update(context)

        # Log error
        await self._log_error(bot_error)

        # Track statistics
        await self._track_error_stats(bot_error)

        # Send notifications for high severity errors
        if bot_error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            await self._send_admin_notification(bot_error)

        # Send user-friendly message
        if event:
            await self._send_user_error_message(event, bot_error)

        return bot_error.correlation_id

    def _convert_to_bot_error(self, error: Exception) -> BotError:
        """Convert standard exception to BotError."""
        # Map common exceptions to BotError types
        if isinstance(error, TelegramAPIError):
            return TelegramError(message=str(error), severity=ErrorSeverity.MEDIUM)
        elif isinstance(error, asyncio.TimeoutError):
            return TimeoutError(message=str(error), severity=ErrorSeverity.MEDIUM)
        elif isinstance(error, (ConnectionError, OSError)):
            return ConnectionError(message=str(error), severity=ErrorSeverity.HIGH)
        elif isinstance(error, ValueError):
            return ValidationError(message=str(error), severity=ErrorSeverity.LOW)
        else:
            return BotError(
                message=str(error),
                error_type=ErrorType.UNKNOWN,
                severity=ErrorSeverity.MEDIUM,
            )

    def _extract_event_context(
        self, event: Union[Message, CallbackQuery]
    ) -> Dict[str, Any]:
        """Extract context from Telegram event."""
        context = {}

        if hasattr(event, "from_user") and event.from_user:
            context["user_id"] = event.from_user.id
            context["username"] = event.from_user.username

        if hasattr(event, "chat") and event.chat:
            context["chat_id"] = event.chat.id
            context["chat_type"] = event.chat.type

        if isinstance(event, Message):
            context["message_id"] = event.message_id
            context["text"] = event.text
        elif isinstance(event, CallbackQuery):
            context["callback_data"] = event.data
            if event.message:
                context["message_id"] = event.message.message_id

        return context

    async def _log_error(self, error: BotError) -> None:
        """Log error with structured logging."""
        log_data = {
            "correlation_id": error.correlation_id,
            "error_type": error.error_type.value,
            "severity": error.severity.value,
            "user_message": error.user_message,
            "context": error.context,
            "timestamp": error.timestamp.isoformat(),
        }

        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(str(error), **log_data)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(str(error), **log_data)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(str(error), **log_data)
        else:
            self.logger.info(str(error), **log_data)

    async def _track_error_stats(self, error: BotError) -> None:
        """Track error statistics."""
        if self.stats_service:
            try:
                await self.stats_service.track_error(
                    error_type=error.error_type.value,
                    severity=error.severity.value,
                    correlation_id=error.correlation_id,
                    context=error.context,
                )
            except Exception as e:
                self.logger.warning(f"Failed to track error stats: {e}")

    async def _send_admin_notification(self, error: BotError) -> None:
        """Send notification to admins for high severity errors."""
        if not self.notification_service or not self.settings:
            return

        try:
            message = self._format_admin_error_message(error)

            # Send to all admin users
            for admin_id in self.settings.telegram.admin_user_ids:
                try:
                    await self.notification_service.send_admin_notification(
                        admin_id=admin_id,
                        message=message,
                        correlation_id=error.correlation_id,
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to send admin notification to {admin_id}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to send admin notifications: {e}")

    def _format_admin_error_message(self, error: BotError) -> str:
        """Format error message for admin notification."""
        severity_emoji = {
            ErrorSeverity.LOW: "ℹ️",
            ErrorSeverity.MEDIUM: "⚠️",
            ErrorSeverity.HIGH: "🚨",
            ErrorSeverity.CRITICAL: "💥",
        }

        emoji = severity_emoji.get(error.severity, "❓")

        message = f"{emoji} <b>Ошибка в боте</b>\n\n"
        message += f"<b>ID:</b> <code>{error.correlation_id}</code>\n"
        message += f"<b>Тип:</b> {error.error_type.value}\n"
        message += f"<b>Серьезность:</b> {error.severity.value}\n"
        message += (
            f"<b>Время:</b> {error.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        )
        message += f"<b>Сообщение:</b> {str(error)}\n"

        if error.context:
            message += f"\n<b>Контекст:</b>\n"
            for key, value in error.context.items():
                if key not in ["traceback"]:  # Skip traceback in notification
                    message += f"• <b>{key}:</b> {value}\n"

        return message

    async def _send_user_error_message(
        self, event: Union[Message, CallbackQuery], error: BotError
    ) -> None:
        """Send user-friendly error message."""
        try:
            message = f"{error.user_message}\n\n"
            message += f"🔍 <b>ID ошибки:</b> <code>{error.correlation_id}</code>\n"
            message += (
                f"<i>Сообщите этот ID поддержке для быстрого решения проблемы.</i>"
            )

            if isinstance(event, Message):
                await event.answer(message, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer(error.user_message, show_alert=True)
                if event.message:
                    await event.message.answer(message, parse_mode="HTML")

        except Exception as e:
            self.logger.warning(f"Failed to send user error message: {e}")

    async def handle_command_error(
        self, error: Exception, event: Union[Message, CallbackQuery], command: str
    ) -> str:
        """Handle command-specific errors.

        Args:
            error: The error that occurred
            event: Telegram event
            command: Command that caused the error

        Returns:
            Correlation ID for tracking
        """
        context = {"command": command}
        return await self.handle_error(error, event, context)

    async def handle_callback_error(
        self, error: Exception, callback_query: CallbackQuery, callback_data: str
    ) -> str:
        """Handle callback query errors.

        Args:
            error: The error that occurred
            callback_query: Callback query event
            callback_data: Callback data that caused the error

        Returns:
            Correlation ID for tracking
        """
        context = {"callback_data": callback_data}
        return await self.handle_error(error, callback_query, context)


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> Optional[ErrorHandler]:
    """Get global error handler instance."""
    return _error_handler


def set_error_handler(error_handler: ErrorHandler) -> None:
    """Set global error handler instance."""
    global _error_handler
    _error_handler = error_handler


# Decorator for error handling
def handle_errors(
    error_type: ErrorType = ErrorType.UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    user_message: Optional[str] = None,
):
    """Decorator for automatic error handling in handlers."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler = get_error_handler()
                if error_handler:
                    # Try to extract event from arguments
                    event = None
                    for arg in args:
                        if isinstance(arg, (Message, CallbackQuery)):
                            event = arg
                            break

                    bot_error = BotError(
                        message=str(e),
                        error_type=error_type,
                        severity=severity,
                        user_message=user_message,
                    )

                    await error_handler.handle_error(bot_error, event)
                raise

        return wrapper

    return decorator
