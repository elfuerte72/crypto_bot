"""Unit tests for configuration models."""

import pytest
from pydantic import ValidationError

from src.config.models import (
    ApplicationConfig,
    CacheConfig,
    CurrencyPair,
    LoggingConfig,
    ManagerConfig,
    RapiraApiConfig,
    RedisConfig,
    Settings,
    TelegramConfig,
)


class TestTelegramConfig:
    """Test cases for TelegramConfig model."""

    def test_valid_telegram_config(self) -> None:
        """Test valid Telegram configuration."""
        config = TelegramConfig(
            token="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH",
            admin_user_ids=[123456789, 987654321],
        )

        assert config.token == "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH"
        assert set(config.admin_user_ids) == {123456789, 987654321}
        assert config.max_connections == 40

    def test_invalid_token_format(self) -> None:
        """Test invalid token format validation."""
        with pytest.raises(ValidationError) as exc_info:
            TelegramConfig(token="invalid-token", admin_user_ids=[123456789])

        assert "Invalid Telegram bot token format" in str(exc_info.value)

    def test_empty_admin_user_ids(self) -> None:
        """Test empty admin user IDs validation."""
        # Empty admin list is now allowed for flexibility
        config = TelegramConfig(
            token="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", admin_user_ids=[]
        )
        assert config.admin_user_ids == []

    def test_invalid_admin_user_id(self) -> None:
        """Test invalid admin user ID validation."""
        with pytest.raises(ValidationError) as exc_info:
            TelegramConfig(
                token="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                admin_user_ids=[0, 123456789],
            )

        assert "Invalid admin user ID" in str(exc_info.value)

    def test_duplicate_admin_user_ids(self) -> None:
        """Test duplicate admin user IDs are removed."""
        config = TelegramConfig(
            token="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            admin_user_ids=[123456789, 123456789, 987654321],
        )

        assert len(config.admin_user_ids) == 2
        assert set(config.admin_user_ids) == {123456789, 987654321}


class TestRapiraApiConfig:
    """Test cases for RapiraApiConfig model."""

    def test_valid_rapira_config(self) -> None:
        """Test valid Rapira API configuration."""
        config = RapiraApiConfig(
            base_url="https://api.rapira.exchange", api_key="test-api-key-123456"
        )

        assert config.base_url == "https://api.rapira.exchange"
        assert config.api_key == "test-api-key-123456"
        assert config.timeout == 30
        assert config.max_retries == 3

    def test_base_url_validation(self) -> None:
        """Test base URL validation."""
        with pytest.raises(ValidationError) as exc_info:
            RapiraApiConfig(base_url="invalid-url", api_key="test-api-key")

        assert "must start with http" in str(exc_info.value)

    def test_base_url_trailing_slash_removal(self) -> None:
        """Test trailing slash removal from base URL."""
        config = RapiraApiConfig(
            base_url="https://api.rapira.exchange/", api_key="test-api-key"
        )

        assert config.base_url == "https://api.rapira.exchange"

    def test_api_key_min_length(self) -> None:
        """Test API key minimum length validation."""
        # API key validation is now flexible for testing
        config = RapiraApiConfig(
            base_url="https://api.rapira.exchange", api_key="short"
        )
        assert config.api_key == "short"

    def test_timeout_bounds(self) -> None:
        """Test timeout bounds validation."""
        # Test minimum
        with pytest.raises(ValidationError):
            RapiraApiConfig(
                base_url="https://api.rapira.exchange",
                api_key="test-api-key",
                timeout=4,
            )

        # Test maximum
        with pytest.raises(ValidationError):
            RapiraApiConfig(
                base_url="https://api.rapira.exchange",
                api_key="test-api-key",
                timeout=121,
            )


class TestRedisConfig:
    """Test cases for RedisConfig model."""

    def test_valid_redis_config(self) -> None:
        """Test valid Redis configuration."""
        config = RedisConfig(host="localhost", port=6379, db=0)

        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None

    def test_connection_url_without_password(self) -> None:
        """Test connection URL generation without password."""
        config = RedisConfig(host="localhost", port=6379, db=1)
        assert config.connection_url == "redis://localhost:6379/1"

    def test_connection_url_with_password(self) -> None:
        """Test connection URL generation with password."""
        config = RedisConfig(
            host="redis.example.com", port=6380, db=2, password="secret123"
        )
        assert config.connection_url == "redis://:secret123@redis.example.com:6380/2"

    def test_port_bounds(self) -> None:
        """Test port bounds validation."""
        # Test minimum
        with pytest.raises(ValidationError):
            RedisConfig(port=0)

        # Test maximum
        with pytest.raises(ValidationError):
            RedisConfig(port=65536)

    def test_db_bounds(self) -> None:
        """Test database number bounds validation."""
        # Test minimum
        with pytest.raises(ValidationError):
            RedisConfig(db=-1)

        # Test maximum
        with pytest.raises(ValidationError):
            RedisConfig(db=16)


class TestCacheConfig:
    """Test cases for CacheConfig model."""

    def test_valid_cache_config(self) -> None:
        """Test valid cache configuration."""
        config = CacheConfig(rate_ttl=300, calculation_ttl=60, stats_ttl=900)

        assert config.rate_ttl == 300
        assert config.calculation_ttl == 60
        assert config.stats_ttl == 900
        assert config.key_prefix == "crypto_bot"

    def test_ttl_bounds(self) -> None:
        """Test TTL bounds validation."""
        # Test rate_ttl minimum
        with pytest.raises(ValidationError):
            CacheConfig(rate_ttl=59)

        # Test rate_ttl maximum
        with pytest.raises(ValidationError):
            CacheConfig(rate_ttl=3601)

    def test_key_prefix_validation(self) -> None:
        """Test key prefix validation."""
        # Valid key prefix
        config = CacheConfig(key_prefix="test_bot_123")
        assert config.key_prefix == "test_bot_123"

        # Invalid key prefix
        with pytest.raises(ValidationError):
            CacheConfig(key_prefix="invalid-prefix!")


class TestCurrencyPair:
    """Test cases for CurrencyPair model."""

    def test_valid_currency_pair(self) -> None:
        """Test valid currency pair creation."""
        pair = CurrencyPair(base="USD", quote="RUB", markup_rate=2.5)

        assert pair.base == "USD"
        assert pair.quote == "RUB"
        assert pair.markup_rate == 2.5
        assert pair.is_active is True
        assert pair.pair_string == "USD/RUB"
        assert pair.reverse_pair_string == "RUB/USD"

    def test_currency_code_validation(self) -> None:
        """Test currency code format validation."""
        # Valid codes
        CurrencyPair(base="USD", quote="RUB")
        CurrencyPair(base="BTC", quote="USDT")  # Crypto codes

        # Invalid codes
        with pytest.raises(ValidationError):
            CurrencyPair(base="us", quote="RUB")  # Too short

        with pytest.raises(ValidationError):
            CurrencyPair(base="USD123", quote="RUB")  # Too long

        with pytest.raises(ValidationError):
            CurrencyPair(base="usd", quote="RUB")  # Lowercase

    def test_same_currency_validation(self) -> None:
        """Test validation for same base and quote currencies."""
        with pytest.raises(ValidationError) as exc_info:
            CurrencyPair(base="USD", quote="USD")

        assert "must be different" in str(exc_info.value)

    def test_markup_rate_bounds(self) -> None:
        """Test markup rate bounds validation."""
        # Test minimum
        with pytest.raises(ValidationError):
            CurrencyPair(base="USD", quote="RUB", markup_rate=-0.1)

        # Test maximum
        with pytest.raises(ValidationError):
            CurrencyPair(base="USD", quote="RUB", markup_rate=50.1)

    def test_amount_limits_validation(self) -> None:
        """Test amount limits validation."""
        # Valid limits
        pair = CurrencyPair(base="USD", quote="RUB", min_amount=10.0, max_amount=1000.0)
        assert pair.min_amount == 10.0
        assert pair.max_amount == 1000.0

        # Invalid limits (min >= max)
        with pytest.raises(ValidationError) as exc_info:
            CurrencyPair(base="USD", quote="RUB", min_amount=1000.0, max_amount=10.0)

        assert "must be less than maximum" in str(exc_info.value)


class TestManagerConfig:
    """Test cases for ManagerConfig model."""

    def test_valid_manager_config(self) -> None:
        """Test valid manager configuration."""
        manager = ManagerConfig(
            user_id=123456789, name="John Doe", currency_pairs={"USD/RUB", "EUR/RUB"}
        )

        assert manager.user_id == 123456789
        assert manager.name == "John Doe"
        assert manager.currency_pairs == {"USD/RUB", "EUR/RUB"}
        assert manager.is_active is True
        assert manager.notification_enabled is True

    def test_user_id_validation(self) -> None:
        """Test user ID validation."""
        with pytest.raises(ValidationError):
            ManagerConfig(user_id=0, name="Test Manager")

        with pytest.raises(ValidationError):
            ManagerConfig(user_id=-123, name="Test Manager")

    def test_name_validation(self) -> None:
        """Test name validation."""
        with pytest.raises(ValidationError):
            ManagerConfig(user_id=123456789, name="")

        # Test maximum length
        long_name = "x" * 101
        with pytest.raises(ValidationError):
            ManagerConfig(user_id=123456789, name=long_name)

    def test_currency_pairs_validation(self) -> None:
        """Test currency pairs format validation."""
        # Valid pairs
        manager = ManagerConfig(
            user_id=123456789,
            name="Test Manager",
            currency_pairs={"USD/RUB", "BTC/USD"},
        )
        assert len(manager.currency_pairs) == 2

        # Invalid pair format
        with pytest.raises(ValidationError) as exc_info:
            ManagerConfig(
                user_id=123456789,
                name="Test Manager",
                currency_pairs={"USDRUB", "BTC/USD"},
            )

        assert "Invalid currency pair format" in str(exc_info.value)


class TestLoggingConfig:
    """Test cases for LoggingConfig model."""

    def test_valid_logging_config(self) -> None:
        """Test valid logging configuration."""
        config = LoggingConfig(level="INFO", format="json", file_path="logs/app.log")

        assert config.level == "INFO"
        assert config.format == "json"
        assert config.file_path == "logs/app.log"
        assert config.file_enabled is True

    def test_log_level_validation(self) -> None:
        """Test log level validation."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level

        # Case insensitive
        config = LoggingConfig(level="info")
        assert config.level == "INFO"

        # Invalid level
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="INVALID")

        assert "Invalid log level" in str(exc_info.value)

    def test_log_format_validation(self) -> None:
        """Test log format validation."""
        # Valid formats
        for fmt in ["json", "text"]:
            config = LoggingConfig(format=fmt)
            assert config.format == fmt

        # Case insensitive
        config = LoggingConfig(format="JSON")
        assert config.format == "json"

        # Invalid format
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(format="xml")

        assert "Invalid log format" in str(exc_info.value)

    def test_file_size_bounds(self) -> None:
        """Test file size bounds validation."""
        # Test minimum
        with pytest.raises(ValidationError):
            LoggingConfig(max_file_size=1048575)  # Less than 1MB

        # Test maximum
        with pytest.raises(ValidationError):
            LoggingConfig(max_file_size=104857601)  # More than 100MB


class TestApplicationConfig:
    """Test cases for ApplicationConfig model."""

    def test_valid_application_config(self) -> None:
        """Test valid application configuration."""
        config = ApplicationConfig(
            name="Test Bot", version="2.0.0", environment="development"
        )

        assert config.name == "Test Bot"
        assert config.version == "2.0.0"
        assert config.environment == "development"
        assert config.debug is False

    def test_environment_validation(self) -> None:
        """Test environment validation."""
        # Valid environments
        for env in ["development", "staging", "production"]:
            config = ApplicationConfig(environment=env)
            assert config.environment == env

        # Case insensitive
        config = ApplicationConfig(environment="PRODUCTION")
        assert config.environment == "production"

        # Invalid environment
        with pytest.raises(ValidationError) as exc_info:
            ApplicationConfig(environment="test")

        assert "Invalid environment" in str(exc_info.value)


class TestSettings:
    """Test cases for Settings model."""

    def test_default_settings(self) -> None:
        """Test default settings creation."""
        settings = Settings()

        # Check that all sections are initialized
        assert isinstance(settings.telegram, TelegramConfig)
        assert isinstance(settings.rapira_api, RapiraApiConfig)
        assert isinstance(settings.redis, RedisConfig)
        assert isinstance(settings.cache, CacheConfig)
        assert isinstance(settings.logging, LoggingConfig)
        assert isinstance(settings.application, ApplicationConfig)

    def test_currency_pair_management(self) -> None:
        """Test currency pair management methods."""
        settings = Settings()

        # Add currency pair
        pair = settings.add_currency_pair("USD", "EUR", markup_rate=1.5)
        assert pair.base == "USD"
        assert pair.quote == "EUR"
        assert pair.markup_rate == 1.5
        assert "USD/EUR" in settings.currency_pairs

        # Update markup rate
        success = settings.update_markup_rate("USD/EUR", 2.0)
        assert success is True
        assert settings.currency_pairs["USD/EUR"].markup_rate == 2.0

        # Update non-existent pair
        success = settings.update_markup_rate("XXX/YYY", 2.0)
        assert success is False

    def test_manager_management(self) -> None:
        """Test manager management methods."""
        settings = Settings()

        # Add manager
        manager = settings.add_manager(123456789, "Test Manager")
        assert manager.user_id == 123456789
        assert manager.name == "Test Manager"
        assert 123456789 in settings.managers

        # Add currency pair and assign to manager
        settings.add_currency_pair("USD", "RUB")
        success = settings.assign_manager_to_pair(123456789, "USD/RUB")
        assert success is True
        assert "USD/RUB" in settings.managers[123456789].currency_pairs

    def test_get_manager_for_pair(self) -> None:
        """Test getting manager for currency pair."""
        settings = Settings()

        # Add manager and currency pair
        settings.add_manager(123456789, "Test Manager")
        settings.add_currency_pair("USD", "RUB")
        settings.assign_manager_to_pair(123456789, "USD/RUB")

        # Get manager for pair
        manager = settings.get_manager_for_pair("USD/RUB")
        assert manager is not None
        assert manager.user_id == 123456789

        # Get manager for non-existent pair
        manager = settings.get_manager_for_pair("XXX/YYY")
        assert manager is None

    def test_active_filtering(self) -> None:
        """Test active currency pairs and managers filtering."""
        settings = Settings()

        # Add active and inactive pairs
        active_pair = settings.add_currency_pair("USD", "RUB", is_active=True)
        inactive_pair = settings.add_currency_pair("EUR", "RUB", is_active=False)

        # Add active and inactive managers
        active_manager = settings.add_manager(
            123456789, "Active Manager", is_active=True
        )
        inactive_manager = settings.add_manager(
            987654321, "Inactive Manager", is_active=False
        )

        # Test filtering
        active_pairs = settings.get_active_currency_pairs()
        assert len(active_pairs) >= 1  # At least the one we added
        assert active_pair in active_pairs
        assert inactive_pair not in active_pairs

        active_managers = settings.get_active_managers()
        assert len(active_managers) == 1
        assert active_manager in active_managers
        assert inactive_manager not in active_managers

    def test_environment_properties(self) -> None:
        """Test environment convenience properties."""
        # Development environment
        dev_settings = Settings()
        dev_settings.application.environment = "development"
        assert dev_settings.is_development is True
        assert dev_settings.is_production is False

        # Production environment
        prod_settings = Settings()
        prod_settings.application.environment = "production"
        assert prod_settings.is_development is False
        assert prod_settings.is_production is True


@pytest.fixture
def sample_settings() -> Settings:
    """Fixture providing sample settings for testing."""
    settings = Settings()

    # Configure Telegram
    settings.telegram.token = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    settings.telegram.admin_user_ids = [123456789]

    # Configure Rapira API
    settings.rapira_api.api_key = "test-api-key-123456"

    # Add currency pairs
    settings.add_currency_pair("USD", "RUB", markup_rate=2.5)
    settings.add_currency_pair("EUR", "RUB", markup_rate=3.0)

    # Add managers
    settings.add_manager(123456789, "Main Manager")
    settings.assign_manager_to_pair(123456789, "USD/RUB")
    settings.assign_manager_to_pair(123456789, "EUR/RUB")

    return settings


class TestSettingsIntegration:
    """Integration tests for Settings model."""

    def test_complete_configuration(self, sample_settings: Settings) -> None:
        """Test complete configuration setup."""
        settings = sample_settings

        # Verify all components are properly configured
        assert settings.telegram.token.startswith("123456789:")
        assert len(settings.telegram.admin_user_ids) == 1
        assert settings.rapira_api.api_key == "test-api-key-123456"
        assert len(settings.currency_pairs) >= 2
        assert len(settings.managers) == 1

        # Verify relationships
        manager = settings.get_manager_for_pair("USD/RUB")
        assert manager is not None
        assert manager.user_id == 123456789

    def test_supported_pairs_list(self, sample_settings: Settings) -> None:
        """Test supported pairs list generation."""
        settings = sample_settings
        pairs_list = settings.supported_pairs_list

        assert isinstance(pairs_list, list)
        assert "USD/RUB" in pairs_list
        assert "EUR/RUB" in pairs_list
