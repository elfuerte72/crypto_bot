"""Structured logging system for the crypto bot.

This module provides comprehensive logging with correlation IDs,
context tracking, and structured output.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import BoundLogger

from config.settings import Settings


# Context variables for correlation tracking
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)
user_id_var: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class CorrelationProcessor:
    """Processor to add correlation IDs to log records."""

    def __call__(
        self, logger: BoundLogger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add correlation context to log records."""
        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            event_dict["correlation_id"] = correlation_id

        # Add user ID if available
        user_id = user_id_var.get()
        if user_id:
            event_dict["user_id"] = user_id

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            event_dict["request_id"] = request_id

        return event_dict


class LoggingMiddleware:
    """Middleware for automatic logging context management."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def __call__(self, handler, event, data):
        """Add logging context for Telegram events."""
        import uuid

        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request_id_var.set(request_id)

        # Extract user ID from event
        user_id = None
        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id
            user_id_var.set(user_id)

        # Log request start
        self.logger.info(
            "Request started",
            event_type=type(event).__name__,
            user_id=user_id,
            request_id=request_id,
        )

        try:
            result = await handler(event, data)

            # Log request success
            self.logger.info("Request completed successfully", request_id=request_id)

            return result

        except Exception as e:
            # Log request error
            self.logger.error(
                "Request failed", error=str(e), request_id=request_id, exc_info=True
            )
            raise

        finally:
            # Clear context
            request_id_var.set(None)
            user_id_var.set(None)


def setup_structured_logging(settings: Settings) -> None:
    """Setup structured logging configuration.

    Args:
        settings: Application settings
    """
    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        CorrelationProcessor(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add appropriate renderer based on environment
    if settings.application.environment == "development":
        # Pretty console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.logging.level.upper()),
    )

    # Set specific logger levels
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)


def get_logger(name: str) -> BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Bound logger instance
    """
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context.

    Args:
        correlation_id: Correlation ID to set
    """
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID.

    Returns:
        Current correlation ID or None
    """
    return correlation_id_var.get()


def set_user_id(user_id: int) -> None:
    """Set user ID for current context.

    Args:
        user_id: User ID to set
    """
    user_id_var.set(user_id)


def get_user_id() -> Optional[int]:
    """Get current user ID.

    Returns:
        Current user ID or None
    """
    return user_id_var.get()


class PerformanceLogger:
    """Logger for performance metrics."""

    def __init__(self, logger: BoundLogger):
        self.logger = logger

    async def log_operation_time(
        self, operation: str, duration: float, success: bool = True, **context: Any
    ) -> None:
        """Log operation performance.

        Args:
            operation: Operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            **context: Additional context
        """
        self.logger.info(
            "Operation performance",
            operation=operation,
            duration_seconds=duration,
            success=success,
            **context,
        )

    async def log_cache_hit(
        self, key: str, hit: bool, ttl: Optional[int] = None
    ) -> None:
        """Log cache hit/miss.

        Args:
            key: Cache key
            hit: Whether it was a hit or miss
            ttl: Time to live if applicable
        """
        self.logger.debug("Cache access", cache_key=key, cache_hit=hit, ttl=ttl)

    async def log_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
        **context: Any,
    ) -> None:
        """Log API call performance.

        Args:
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            duration: Call duration in seconds
            **context: Additional context
        """
        self.logger.info(
            "API call",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_seconds=duration,
            success=200 <= status_code < 300,
            **context,
        )


class BusinessEventLogger:
    """Logger for business events."""

    def __init__(self, logger: BoundLogger):
        self.logger = logger

    async def log_rate_request(
        self,
        user_id: int,
        currency_pair: str,
        rate: Optional[float] = None,
        **context: Any,
    ) -> None:
        """Log rate request event.

        Args:
            user_id: User ID who requested rate
            currency_pair: Currency pair requested
            rate: Rate value if successful
            **context: Additional context
        """
        self.logger.info(
            "Rate requested",
            event_type="rate_request",
            user_id=user_id,
            currency_pair=currency_pair,
            rate=rate,
            **context,
        )

    async def log_calculation_request(
        self,
        user_id: int,
        currency_pair: str,
        amount: float,
        result: Optional[float] = None,
        **context: Any,
    ) -> None:
        """Log calculation request event.

        Args:
            user_id: User ID who requested calculation
            currency_pair: Currency pair for calculation
            amount: Amount to calculate
            result: Calculation result if successful
            **context: Additional context
        """
        self.logger.info(
            "Calculation requested",
            event_type="calculation_request",
            user_id=user_id,
            currency_pair=currency_pair,
            amount=amount,
            result=result,
            **context,
        )

    async def log_admin_action(
        self, admin_id: int, action: str, target: Optional[str] = None, **context: Any
    ) -> None:
        """Log admin action event.

        Args:
            admin_id: Admin user ID
            action: Action performed
            target: Target of the action
            **context: Additional context
        """
        self.logger.info(
            "Admin action",
            event_type="admin_action",
            admin_id=admin_id,
            action=action,
            target=target,
            **context,
        )


class SecurityEventLogger:
    """Logger for security events."""

    def __init__(self, logger: BoundLogger):
        self.logger = logger

    async def log_unauthorized_access(
        self, user_id: int, action: str, **context: Any
    ) -> None:
        """Log unauthorized access attempt.

        Args:
            user_id: User ID who attempted access
            action: Action that was attempted
            **context: Additional context
        """
        self.logger.warning(
            "Unauthorized access attempt",
            event_type="unauthorized_access",
            user_id=user_id,
            action=action,
            **context,
        )

    async def log_rate_limit_exceeded(
        self, user_id: int, endpoint: str, **context: Any
    ) -> None:
        """Log rate limit exceeded event.

        Args:
            user_id: User ID who exceeded rate limit
            endpoint: Endpoint that was rate limited
            **context: Additional context
        """
        self.logger.warning(
            "Rate limit exceeded",
            event_type="rate_limit_exceeded",
            user_id=user_id,
            endpoint=endpoint,
            **context,
        )

    async def log_suspicious_activity(
        self, user_id: int, activity: str, **context: Any
    ) -> None:
        """Log suspicious activity.

        Args:
            user_id: User ID associated with activity
            activity: Description of suspicious activity
            **context: Additional context
        """
        self.logger.warning(
            "Suspicious activity detected",
            event_type="suspicious_activity",
            user_id=user_id,
            activity=activity,
            **context,
        )


def get_performance_logger(name: str) -> PerformanceLogger:
    """Get performance logger instance.

    Args:
        name: Logger name

    Returns:
        Performance logger instance
    """
    logger = get_logger(name)
    return PerformanceLogger(logger)


def get_business_event_logger(name: str) -> BusinessEventLogger:
    """Get business event logger instance.

    Args:
        name: Logger name

    Returns:
        Business event logger instance
    """
    logger = get_logger(name)
    return BusinessEventLogger(logger)


def get_security_event_logger(name: str) -> SecurityEventLogger:
    """Get security event logger instance.

    Args:
        name: Logger name

    Returns:
        Security event logger instance
    """
    logger = get_logger(name)
    return SecurityEventLogger(logger)
