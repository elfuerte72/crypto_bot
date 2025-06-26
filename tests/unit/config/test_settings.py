"""Unit tests for settings module."""

from typing import Any
from unittest.mock import patch

import pytest

from src.config.settings import Settings, get_settings


class TestSettingsBackwardCompatibility:
    """Test backward compatibility of Settings class."""

    def test_backward_compatible_properties(self) -> None:
        """Test that backward compatible properties work correctly."""
        settings = Settings()

        # Set up test data
        settings.telegram.token = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        settings.telegram.admin_user_ids = [123456789, 987654321]
        settings.rapira_api.api_key = "test-api-key"
        settings.redis.host = "redis.example.com"
        settings.redis.port = 6380
        settings.redis.db = 2
        settings.redis.password = "secret123"
        settings.cache.rate_ttl = 600
        settings.logging.level = "DEBUG"
        settings.logging.format = "text"
        settings.application.debug = True
        settings.application.environment = "development"

        # Test backward compatible properties
        assert settings.bot_token == "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        assert settings.admin_user_id == 123456789  # First admin ID
        assert settings.rapira_api_url == settings.rapira_api.base_url
        assert settings.rapira_api_key == "test-api-key"
        assert settings.redis_host == "redis.example.com"
        assert settings.redis_port == 6380
        assert settings.redis_db == 2
        assert settings.redis_password == "secret123"
        assert settings.rate_cache_ttl == 600
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "text"
        assert settings.debug is True
        assert settings.environment == "development"
        assert settings.redis_url == "redis://:secret123@redis.example.com:6380/2"

    def test_admin_user_id_empty_list(self) -> None:
        """Test admin_user_id property with empty admin list."""
        settings = Settings()
        settings.telegram.admin_user_ids = []

        assert settings.admin_user_id == 0

    def test_redis_password_empty(self) -> None:
        """Test redis_password property when password is None."""
        settings = Settings()
        settings.redis.password = None

        assert settings.redis_password == ""

    def test_supported_pairs_property(self) -> None:
        """Test supported_pairs property returns comma-separated string."""
        settings = Settings()
        settings.add_currency_pair("USD", "RUB")
        settings.add_currency_pair("EUR", "USD")

        supported_pairs = settings.supported_pairs
        assert isinstance(supported_pairs, str)
        assert "USD/RUB" in supported_pairs
        assert "EUR/USD" in supported_pairs
        assert "," in supported_pairs

    def test_currency_pairs_list_property(self) -> None:
        """Test currency_pairs_list property."""
        settings = Settings()
        settings.add_currency_pair("USD", "RUB")
        settings.add_currency_pair("EUR", "USD")

        pairs_list = settings.currency_pairs_list
        assert isinstance(pairs_list, list)
        assert "USD/RUB" in pairs_list
        assert "EUR/USD" in pairs_list


class TestSettingsInitialization:
    """Test Settings initialization and default setup."""

    def test_default_currency_pairs_initialization(self) -> None:
        """Test that default currency pairs are initialized."""
        settings = Settings()

        # Should have default currency pairs
        assert len(settings.currency_pairs) > 0

        # Check some expected default pairs
        expected_pairs = ["USD/RUB", "EUR/RUB", "BTC/USD", "ETH/USD"]
        for pair in expected_pairs:
            assert pair in settings.currency_pairs
            assert settings.currency_pairs[pair].is_active is True
            assert (
                settings.currency_pairs[pair].markup_rate
                == settings.default_markup_rate
            )

    def test_no_default_pairs_when_configured(self) -> None:
        """Test that default pairs are not added when pairs are already configured."""
        settings = Settings()
        # Clear default pairs
        settings.currency_pairs.clear()

        # Add custom pair
        settings.add_currency_pair("BTC", "ETH", markup_rate=1.0)

        # Create new settings instance - should not add defaults
        new_settings = Settings()
        new_settings.currency_pairs = {"BTC/ETH": settings.currency_pairs["BTC/ETH"]}

        # Should only have the custom pair
        assert len(new_settings.currency_pairs) == 1
        assert "BTC/ETH" in new_settings.currency_pairs

    @patch(
        "src.config.settings.BusinessRuleValidators.validate_currency_pair_consistency"
    )
    @patch("src.config.settings.BusinessRuleValidators.validate_manager_load_balance")
    @patch(
        "src.config.settings.BusinessRuleValidators.validate_environment_consistency"
    )
    def test_business_rules_validation_called(
        self, mock_env: Any, mock_load: Any, mock_consistency: Any
    ) -> None:
        """Test that business rules validation is called during initialization."""
        Settings()

        mock_consistency.assert_called_once()
        mock_load.assert_called_once()
        mock_env.assert_called_once()

    @patch(
        "src.config.settings.BusinessRuleValidators.validate_currency_pair_consistency"
    )
    def test_business_rules_validation_warning_handling(
        self, mock_validator: Any
    ) -> None:
        """Test that business rules validation warnings are handled properly."""
        mock_validator.side_effect = ValueError("Test validation error")

        # Should not raise exception, but should issue warning
        with pytest.warns(UserWarning, match="Business rule validation warning"):
            settings = Settings()

        # Settings should still be created
        assert isinstance(settings, Settings)


class TestSettingsExtendedFunctionality:
    """Test extended functionality of Settings class."""

    def test_currency_pair_management_extended(self) -> None:
        """Test extended currency pair management functionality."""
        settings = Settings()

        # Test adding pair with all parameters
        pair = settings.add_currency_pair(
            "BTC",
            "EUR",
            markup_rate=3.5,
            is_active=False,
            min_amount=0.001,
            max_amount=10.0,
        )

        assert pair.base == "BTC"
        assert pair.quote == "EUR"
        assert pair.markup_rate == 3.5
        assert pair.is_active is False
        assert pair.min_amount == 0.001
        assert pair.max_amount == 10.0
        assert "BTC/EUR" in settings.currency_pairs

    def test_manager_management_extended(self) -> None:
        """Test extended manager management functionality."""
        settings = Settings()

        # Test adding manager with all parameters
        manager = settings.add_manager(
            123456789,
            "Test Manager",
            currency_pairs={"USD/RUB", "EUR/RUB"},
            is_active=False,
            notification_enabled=False,
        )

        assert manager.user_id == 123456789
        assert manager.name == "Test Manager"
        assert manager.currency_pairs == {"USD/RUB", "EUR/RUB"}
        assert manager.is_active is False
        assert manager.notification_enabled is False
        assert 123456789 in settings.managers

    def test_get_manager_for_pair_with_default(self) -> None:
        """Test getting manager for pair with default manager fallback."""
        settings = Settings()

        # Set default manager
        settings.default_manager_id = 999999999
        settings.add_manager(999999999, "Default Manager")

        # Add currency pair without specific manager
        settings.add_currency_pair("TEST", "COIN")

        # Should return default manager
        manager = settings.get_manager_for_pair("TEST/COIN")
        assert manager is not None
        assert manager.user_id == 999999999

    def test_get_manager_for_pair_no_default(self) -> None:
        """Test getting manager for pair without default manager."""
        settings = Settings()
        settings.default_manager_id = None

        # Add currency pair without specific manager
        settings.add_currency_pair("TEST", "COIN")

        # Should return None
        manager = settings.get_manager_for_pair("TEST/COIN")
        assert manager is None

    def test_active_filtering_comprehensive(self) -> None:
        """Test comprehensive active filtering functionality."""
        settings = Settings()

        # Clear default pairs for clean test
        settings.currency_pairs.clear()
        settings.managers.clear()

        # Add mix of active and inactive pairs
        active_pair1 = settings.add_currency_pair("USD", "RUB", is_active=True)
        active_pair2 = settings.add_currency_pair("EUR", "RUB", is_active=True)
        inactive_pair = settings.add_currency_pair("BTC", "RUB", is_active=False)

        # Add mix of active and inactive managers
        active_manager1 = settings.add_manager(
            111111111, "Active Manager 1", is_active=True
        )
        active_manager2 = settings.add_manager(
            222222222, "Active Manager 2", is_active=True
        )
        inactive_manager = settings.add_manager(
            333333333, "Inactive Manager", is_active=False
        )

        # Test active pairs filtering
        active_pairs = settings.get_active_currency_pairs()
        assert len(active_pairs) == 2
        assert active_pair1 in active_pairs
        assert active_pair2 in active_pairs
        assert inactive_pair not in active_pairs

        # Test active managers filtering
        active_managers = settings.get_active_managers()
        assert len(active_managers) == 2
        assert active_manager1 in active_managers
        assert active_manager2 in active_managers
        assert inactive_manager not in active_managers

    def test_environment_properties_comprehensive(self) -> None:
        """Test comprehensive environment properties."""
        settings = Settings()

        # Test all environments
        environments = ["development", "staging", "production"]

        for env in environments:
            settings.application.environment = env

            if env == "development":
                assert settings.is_development is True
                assert settings.is_production is False
            elif env == "production":
                assert settings.is_development is False
                assert settings.is_production is True
            else:  # staging
                assert settings.is_development is False
                assert settings.is_production is False


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self) -> None:
        """Test that get_settings returns the same instance (cached)."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance due to @lru_cache
        assert settings1 is settings2

    @patch("src.config.settings.Settings")
    def test_get_settings_cache_behavior(self, mock_settings_class: Any) -> None:
        """Test caching behavior of get_settings."""
        mock_instance = mock_settings_class.return_value

        # Clear cache first
        get_settings.cache_clear()

        # First call should create instance
        result1 = get_settings()
        assert result1 is mock_instance
        assert mock_settings_class.call_count == 1

        # Second call should return cached instance
        result2 = get_settings()
        assert result2 is mock_instance
        assert mock_settings_class.call_count == 1  # Should not be called again


class TestSettingsIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_complete_bot_setup_scenario(self) -> None:
        """Test complete bot setup scenario."""
        settings = Settings()

        # Configure Telegram
        settings.telegram.token = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        settings.telegram.admin_user_ids = [123456789]

        # Configure API
        settings.rapira_api.api_key = "production-api-key"
        settings.rapira_api.timeout = 60

        # Configure Redis
        settings.redis.host = "redis.production.com"
        settings.redis.password = "secure-password"

        # Set up currency pairs with different markup rates
        settings.add_currency_pair("USD", "RUB", markup_rate=2.0)
        settings.add_currency_pair("EUR", "RUB", markup_rate=2.5)
        settings.add_currency_pair("BTC", "USD", markup_rate=1.5)

        # Set up managers
        settings.add_manager(111111111, "USD Manager")
        settings.add_manager(222222222, "EUR Manager")
        settings.add_manager(333333333, "Crypto Manager")

        # Assign currency pairs to managers
        settings.assign_manager_to_pair(111111111, "USD/RUB")
        settings.assign_manager_to_pair(222222222, "EUR/RUB")
        settings.assign_manager_to_pair(333333333, "BTC/USD")

        # Verify complete setup
        assert len(settings.currency_pairs) >= 3
        assert len(settings.managers) == 3

        # Verify manager assignments
        usd_manager_retrieved = settings.get_manager_for_pair("USD/RUB")
        assert usd_manager_retrieved is not None
        assert usd_manager_retrieved.user_id == 111111111

        eur_manager_retrieved = settings.get_manager_for_pair("EUR/RUB")
        assert eur_manager_retrieved is not None
        assert eur_manager_retrieved.user_id == 222222222

        crypto_manager_retrieved = settings.get_manager_for_pair("BTC/USD")
        assert crypto_manager_retrieved is not None
        assert crypto_manager_retrieved.user_id == 333333333

        # Verify configuration access
        assert settings.bot_token.startswith("123456789:")
        assert settings.redis_url.startswith("redis://:secure-password@")
        assert "USD/RUB" in settings.supported_pairs

    def test_production_environment_scenario(self) -> None:
        """Test production environment configuration scenario."""
        settings = Settings()

        # Configure for production
        settings.application.environment = "production"
        settings.application.debug = False
        settings.logging.level = "WARNING"
        settings.logging.format = "json"

        # Configure secure Redis
        settings.redis.host = "redis-cluster.internal"
        settings.redis.password = "super-secure-password"
        settings.redis.max_connections = 50

        # Configure API with retries
        settings.rapira_api.max_retries = 5
        settings.rapira_api.timeout = 30
        settings.rapira_api.backoff_factor = 2.0

        # Configure caching for production load
        settings.cache.rate_ttl = 180  # 3 minutes
        settings.cache.calculation_ttl = 30

        # Verify production settings
        assert settings.is_production is True
        assert settings.is_development is False
        assert settings.debug is False
        assert settings.log_level == "WARNING"
        assert settings.redis.max_connections == 50
        assert settings.cache.rate_ttl == 180

    def test_development_environment_scenario(self) -> None:
        """Test development environment configuration scenario."""
        settings = Settings()

        # Configure for development
        settings.application.environment = "development"
        settings.application.debug = True
        settings.logging.level = "DEBUG"
        settings.logging.format = "text"

        # Configure local Redis
        settings.redis.host = "localhost"
        settings.redis.password = None
        settings.redis.db = 1  # Use different DB for dev

        # Configure API for development
        settings.rapira_api.base_url = "https://api-dev.rapira.exchange"
        settings.rapira_api.timeout = 10

        # Configure shorter cache times for development
        settings.cache.rate_ttl = 60
        settings.cache.calculation_ttl = 10

        # Verify development settings
        assert settings.is_development is True
        assert settings.is_production is False
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.redis.password is None
        assert settings.redis_url == "redis://localhost:6379/1"
        assert settings.cache.rate_ttl == 60
