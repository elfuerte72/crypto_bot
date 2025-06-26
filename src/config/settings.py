"""Application settings and configuration."""

from functools import lru_cache

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Telegram Bot Configuration
    bot_token: str = Field(default="", description="Telegram Bot API token")
    admin_user_id: int = Field(default=0, description="Admin user ID")

    # Rapira API Configuration
    rapira_api_url: str = Field(
        default="https://api.rapira.exchange", description="Rapira API base URL"
    )
    rapira_api_key: str = Field(default="", description="Rapira API key")

    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: str = Field(default="", description="Redis password")

    # Cache Configuration
    rate_cache_ttl: int = Field(default=300, description="Rate cache TTL in seconds")

    # Markup Configuration
    default_markup_rate: float = Field(
        default=2.5, description="Default markup rate in percentage"
    )

    # Currency Pairs
    supported_pairs: str = Field(
        default="USD/RUB,EUR/RUB,USD/EUR,BTC/USD,ETH/USD,USDT/RUB,BTC/RUB,ETH/RUB",
        description="Comma-separated list of supported currency pairs",
    )

    # Manager Configuration
    default_manager_id: int = Field(default=0, description="Default manager user ID")

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format")

    # Application Configuration
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="production", description="Environment")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("supported_pairs")
    def validate_supported_pairs(cls, v: str) -> str:
        """Validate supported currency pairs format."""
        pairs = [pair.strip() for pair in v.split(",")]
        for pair in pairs:
            if "/" not in pair:
                raise ValueError(f"Invalid currency pair format: {pair}")
        return v

    @property
    def currency_pairs_list(self) -> list[str]:
        """Get list of supported currency pairs."""
        return [pair.strip() for pair in self.supported_pairs.split(",")]

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()
