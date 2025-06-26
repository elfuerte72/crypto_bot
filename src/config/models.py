"""Configuration models for the crypto bot application.

This module provides comprehensive Pydantic models for all configuration aspects
of the crypto bot, including validation, type safety, and environment variable management.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from .validators import ConfigurationValidators


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    token: str = Field(default="", description="Telegram Bot API token", min_length=0)
    admin_user_ids: list[int] = Field(
        default_factory=list, description="List of admin user IDs with full access"
    )
    webhook_url: str | None = Field(
        default=None, description="Webhook URL for production deployment"
    )
    webhook_secret: str | None = Field(
        default=None, description="Webhook secret token for security"
    )
    max_connections: int = Field(
        default=40, ge=1, le=100, description="Maximum webhook connections"
    )

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate Telegram bot token format."""
        if v:  # Only validate if token is provided
            return ConfigurationValidators.validate_telegram_token(v)
        return v

    @field_validator("admin_user_ids")
    @classmethod
    def validate_admin_user_ids(cls, v: list[int]) -> list[int]:
        """Validate admin user IDs are positive integers."""
        for user_id in v:
            if user_id <= 0:
                raise ValueError(f"Invalid admin user ID: {user_id}")

        return list(set(v))  # Remove duplicates


class RapiraApiConfig(BaseModel):
    """Rapira API configuration."""

    base_url: str = Field(
        default="https://api.rapira.exchange", description="Rapira API base URL"
    )
    api_key: str = Field(
        default="", description="Rapira API authentication key", min_length=0
    )
    timeout: int = Field(
        default=30, ge=5, le=120, description="API request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum number of retry attempts"
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Initial delay between retries in seconds",
    )
    backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Exponential backoff factor for retries",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate API base URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("API base URL must start with http:// or https://")
        return v.rstrip("/")


class RedisConfig(BaseModel):
    """Redis cache configuration."""

    host: str = Field(default="localhost", description="Redis server host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis server port")
    db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    password: str | None = Field(
        default=None, description="Redis authentication password"
    )
    socket_timeout: float = Field(
        default=5.0, ge=1.0, le=30.0, description="Socket timeout in seconds"
    )
    socket_connect_timeout: float = Field(
        default=5.0, ge=1.0, le=30.0, description="Socket connection timeout in seconds"
    )
    max_connections: int = Field(
        default=10, ge=1, le=100, description="Maximum Redis connection pool size"
    )

    @property
    def connection_url(self) -> str:
        """Generate Redis connection URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class CacheConfig(BaseModel):
    """Cache configuration settings."""

    rate_ttl: int = Field(
        default=300, ge=60, le=3600, description="Exchange rate cache TTL in seconds"
    )
    calculation_ttl: int = Field(
        default=60, ge=10, le=300, description="Calculation result cache TTL in seconds"
    )
    stats_ttl: int = Field(
        default=900, ge=300, le=3600, description="Statistics cache TTL in seconds"
    )
    key_prefix: str = Field(
        default="crypto_bot", description="Cache key prefix for namespacing"
    )

    @field_validator("key_prefix")
    @classmethod
    def validate_key_prefix(cls, v: str) -> str:
        """Validate cache key prefix format."""
        if not v.isalnum() and "_" not in v:
            raise ValueError(
                "Cache key prefix must contain only alphanumeric characters and underscores"
            )
        return v


class CurrencyPair(BaseModel):
    """Currency pair configuration."""

    base: str = Field(
        ...,
        description="Base currency code",
        min_length=3,
        max_length=5,
        pattern=r"^[A-Z]{3,5}$",
    )
    quote: str = Field(
        ...,
        description="Quote currency code",
        min_length=3,
        max_length=5,
        pattern=r"^[A-Z]{3,5}$",
    )
    markup_rate: float = Field(
        default=2.5, ge=0.0, le=50.0, description="Markup rate in percentage"
    )
    is_active: bool = Field(
        default=True, description="Whether the pair is active for trading"
    )
    min_amount: float | None = Field(
        default=None, ge=0.0, description="Minimum transaction amount"
    )
    max_amount: float | None = Field(
        default=None, ge=0.0, description="Maximum transaction amount"
    )

    @property
    def pair_string(self) -> str:
        """Get currency pair as string (e.g., 'USD/RUB')."""
        return f"{self.base}/{self.quote}"

    @property
    def reverse_pair_string(self) -> str:
        """Get reverse currency pair as string (e.g., 'RUB/USD')."""
        return f"{self.quote}/{self.base}"

    @field_validator("quote")
    @classmethod
    def validate_different_currencies(cls, v: str, info: Any) -> str:
        """Ensure base and quote currencies are different."""
        if (
            hasattr(info, "data")
            and info.data
            and "base" in info.data
            and v == info.data["base"]
        ):
            raise ValueError("Base and quote currencies must be different")
        return v

    @model_validator(mode="after")
    def validate_amount_limits(self) -> CurrencyPair:
        """Validate amount limits consistency."""
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount >= self.max_amount
        ):
            raise ValueError("Minimum amount must be less than maximum amount")

        return self


class ManagerConfig(BaseModel):
    """Manager configuration for currency pairs."""

    user_id: int = Field(..., gt=0, description="Telegram user ID of the manager")
    name: str = Field(
        ..., min_length=1, max_length=100, description="Manager display name"
    )
    currency_pairs: set[str] = Field(
        default_factory=set, description="Set of currency pairs this manager handles"
    )
    is_active: bool = Field(default=True, description="Whether the manager is active")
    notification_enabled: bool = Field(
        default=True, description="Whether to send notifications to this manager"
    )

    @field_validator("currency_pairs")
    @classmethod
    def validate_currency_pairs(cls, v: set[str]) -> set[str]:
        """Validate currency pair format."""
        for pair in v:
            if "/" not in pair or len(pair.split("/")) != 2:
                raise ValueError(f"Invalid currency pair format: {pair}")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Log format (json or text)")
    file_enabled: bool = Field(default=True, description="Enable file logging")
    file_path: str = Field(default="logs/crypto_bot.log", description="Log file path")
    max_file_size: int = Field(
        default=10485760,  # 10MB
        ge=1048576,  # 1MB
        le=104857600,  # 100MB
        description="Maximum log file size in bytes",
    )
    backup_count: int = Field(
        default=5, ge=1, le=20, description="Number of log file backups to keep"
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = {"json", "text"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v_lower


class ApplicationConfig(BaseModel):
    """General application configuration."""

    name: str = Field(default="Crypto Bot", description="Application name")
    version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(
        default="production",
        description="Environment (development, staging, production)",
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    timezone: str = Field(default="UTC", description="Application timezone")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "staging", "production"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v_lower


class Settings(BaseSettings):
    """Main application settings combining all configuration models."""

    # Configuration sections
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    rapira_api: RapiraApiConfig = Field(default_factory=RapiraApiConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    application: ApplicationConfig = Field(default_factory=ApplicationConfig)

    # Currency pairs and managers
    currency_pairs: dict[str, CurrencyPair] = Field(
        default_factory=dict, description="Configured currency pairs"
    )
    managers: dict[int, ManagerConfig] = Field(
        default_factory=dict, description="Configured managers by user ID"
    )

    # Default settings for backward compatibility
    default_markup_rate: float = Field(
        default=2.5,
        ge=0.0,
        le=50.0,
        description="Default markup rate for new currency pairs",
    )
    default_manager_id: int | None = Field(
        default=None, description="Default manager user ID for unassigned pairs"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "env_nested_delimiter": "__",
        "extra": "allow",
    }

    def get_currency_pair(self, pair_string: str) -> CurrencyPair | None:
        """Get currency pair configuration by pair string."""
        return self.currency_pairs.get(pair_string)

    def get_manager_for_pair(self, pair_string: str) -> ManagerConfig | None:
        """Get manager assigned to a specific currency pair."""
        for manager in self.managers.values():
            if pair_string in manager.currency_pairs:
                return manager

        # Return default manager if configured
        if self.default_manager_id:
            return self.managers.get(self.default_manager_id)

        return None

    def get_active_currency_pairs(self) -> list[CurrencyPair]:
        """Get list of active currency pairs."""
        return [pair for pair in self.currency_pairs.values() if pair.is_active]

    def get_active_managers(self) -> list[ManagerConfig]:
        """Get list of active managers."""
        return [manager for manager in self.managers.values() if manager.is_active]

    def add_currency_pair(self, base: str, quote: str, **kwargs: Any) -> CurrencyPair:
        """Add a new currency pair configuration."""
        pair = CurrencyPair(base=base, quote=quote, **kwargs)
        self.currency_pairs[pair.pair_string] = pair
        return pair

    def add_manager(self, user_id: int, name: str, **kwargs: Any) -> ManagerConfig:
        """Add a new manager configuration."""
        manager = ManagerConfig(user_id=user_id, name=name, **kwargs)
        self.managers[user_id] = manager
        return manager

    def update_markup_rate(self, pair_string: str, markup_rate: float) -> bool:
        """Update markup rate for a currency pair."""
        if pair_string in self.currency_pairs:
            self.currency_pairs[pair_string].markup_rate = markup_rate
            return True
        return False

    def assign_manager_to_pair(self, manager_id: int, pair_string: str) -> bool:
        """Assign a manager to a currency pair."""
        if manager_id in self.managers and pair_string in self.currency_pairs:
            self.managers[manager_id].currency_pairs.add(pair_string)
            return True
        return False

    @property
    def supported_pairs_list(self) -> list[str]:
        """Get list of all supported currency pair strings."""
        return list(self.currency_pairs.keys())

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.application.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.application.environment == "production"
