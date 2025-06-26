"""Application settings and configuration.

This module provides a simplified interface to the comprehensive configuration models
and maintains backward compatibility with the existing codebase.
"""

from functools import lru_cache
from typing import Any

from .models import (
    ApplicationConfig,
    CacheConfig,
    CurrencyPair,
    LoggingConfig,
    ManagerConfig,
    RapiraApiConfig,
    RedisConfig,
    Settings as BaseSettings,
    TelegramConfig,
)
from .validators import BusinessRuleValidators, ConfigurationValidators


class Settings(BaseSettings):
    """Enhanced application settings with validation and business rules."""

    def __init__(self, **data: Any) -> None:
        """Initialize settings with validation."""
        super().__init__(**data)

        # Initialize default currency pairs if none configured
        if not self.currency_pairs:
            self._initialize_default_currency_pairs()

        # Validate business rules
        self._validate_business_rules()

    def _initialize_default_currency_pairs(self) -> None:
        """Initialize default currency pairs from legacy configuration."""
        default_pairs = [
            ("USD", "RUB"),
            ("EUR", "RUB"),
            ("USD", "EUR"),
            ("BTC", "USD"),
            ("ETH", "USD"),
            ("USDT", "RUB"),
            ("BTC", "RUB"),
            ("ETH", "RUB"),
        ]

        for base, quote in default_pairs:
            self.add_currency_pair(
                base=base,
                quote=quote,
                markup_rate=self.default_markup_rate,
                is_active=True,
            )

    def _validate_business_rules(self) -> None:
        """Validate business rules and consistency."""
        try:
            BusinessRuleValidators.validate_currency_pair_consistency(
                self.currency_pairs, self.managers
            )
            BusinessRuleValidators.validate_manager_load_balance(self.managers)
            BusinessRuleValidators.validate_environment_consistency(
                self.application.environment, self.application.debug, self.logging.level
            )
        except Exception as e:
            import warnings

            warnings.warn(
                f"Business rule validation warning: {e}", UserWarning, stacklevel=2
            )

    # Backward compatibility properties
    @property
    def bot_token(self) -> str:
        """Get Telegram bot token (backward compatibility)."""
        return self.telegram.token

    @property
    def admin_user_id(self) -> int:
        """Get first admin user ID (backward compatibility)."""
        if self.telegram.admin_user_ids:
            return self.telegram.admin_user_ids[0]
        return 0

    @property
    def rapira_api_url(self) -> str:
        """Get Rapira API URL (backward compatibility)."""
        return self.rapira_api.base_url

    @property
    def rapira_api_key(self) -> str:
        """Get Rapira API key (backward compatibility)."""
        return self.rapira_api.api_key

    @property
    def redis_host(self) -> str:
        """Get Redis host (backward compatibility)."""
        return self.redis.host

    @property
    def redis_port(self) -> int:
        """Get Redis port (backward compatibility)."""
        return self.redis.port

    @property
    def redis_db(self) -> int:
        """Get Redis database (backward compatibility)."""
        return self.redis.db

    @property
    def redis_password(self) -> str:
        """Get Redis password (backward compatibility)."""
        return self.redis.password or ""

    @property
    def rate_cache_ttl(self) -> int:
        """Get rate cache TTL (backward compatibility)."""
        return self.cache.rate_ttl

    @property
    def supported_pairs(self) -> str:
        """Get supported pairs as comma-separated string (backward compatibility)."""
        return ",".join(self.supported_pairs_list)

    @property
    def log_level(self) -> str:
        """Get log level (backward compatibility)."""
        return self.logging.level

    @property
    def log_format(self) -> str:
        """Get log format (backward compatibility)."""
        return self.logging.format

    @property
    def debug(self) -> bool:
        """Get debug flag (backward compatibility)."""
        return self.application.debug

    @property
    def environment(self) -> str:
        """Get environment (backward compatibility)."""
        return self.application.environment

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL (backward compatibility)."""
        return self.redis.connection_url

    @property
    def currency_pairs_list(self) -> list[str]:
        """Get list of supported currency pairs (backward compatibility)."""
        return self.supported_pairs_list


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()


# Export commonly used types for convenience
__all__ = [
    "ApplicationConfig",
    "BusinessRuleValidators",
    "CacheConfig",
    "ConfigurationValidators",
    "CurrencyPair",
    "LoggingConfig",
    "ManagerConfig",
    "RapiraApiConfig",
    "RedisConfig",
    "Settings",
    "TelegramConfig",
    "get_settings",
]
