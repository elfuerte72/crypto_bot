"""Unit tests for configuration validators."""

import warnings
from typing import Any
from unittest.mock import patch

import pytest

from src.config.validators import BusinessRuleValidators, ConfigurationValidators


class TestConfigurationValidators:
    """Test cases for ConfigurationValidators."""

    def test_validate_telegram_token_valid(self) -> None:
        """Test valid Telegram token validation."""
        valid_tokens = [
            "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-ABCDEF",
            "12345678:ABCdefGHIjklMNOpqrsTUVwxyz-ABCDEFG",
        ]

        for token in valid_tokens:
            result = ConfigurationValidators.validate_telegram_token(token)
            assert result == token

    def test_validate_telegram_token_invalid(self) -> None:
        """Test invalid Telegram token validation."""
        invalid_tokens = [
            "",
            "invalid-token",
            "123456789",  # Missing auth token
            "123456789:",  # Empty auth token
            "123456789:short",  # Auth token too short (less than 20 chars)
            "1234567:ABCdefGHIjklMNOpqrsTUVwxyz",  # Bot ID too short (less than 8 digits)
            "1234567890123:ABCdefGHIjklMNOpqrsTUVwxyz",  # Bot ID too long (more than 12 digits)
        ]

        for token in invalid_tokens:
            with pytest.raises(ValueError) as exc_info:
                ConfigurationValidators.validate_telegram_token(token)

            if token:  # Don't check message for empty token
                assert "Invalid Telegram bot token format" in str(exc_info.value)

    def test_validate_url_valid(self) -> None:
        """Test valid URL validation."""
        valid_urls = [
            "https://api.example.com",
            "http://localhost:8080",
            "https://api.example.com/v1",
            "https://api.example.com/",  # Should remove trailing slash
        ]

        for url in valid_urls:
            result = ConfigurationValidators.validate_url(url)
            assert result == url.rstrip("/")

    def test_validate_url_invalid(self) -> None:
        """Test invalid URL validation."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",  # Invalid scheme
            "https://",  # No domain
            "api.example.com",  # No scheme
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_url(url)

    def test_validate_url_custom_schemes(self) -> None:
        """Test URL validation with custom schemes."""
        # Allow FTP
        result = ConfigurationValidators.validate_url(
            "ftp://files.example.com", schemes=["ftp", "ftps"]
        )
        assert result == "ftp://files.example.com"

        # Reject HTTP when only HTTPS allowed
        with pytest.raises(ValueError) as exc_info:
            ConfigurationValidators.validate_url(
                "http://api.example.com", schemes=["https"]
            )
        assert "scheme must be one of: https" in str(exc_info.value)

    def test_validate_currency_code_valid(self) -> None:
        """Test valid currency code validation."""
        valid_codes = [
            "USD",
            "EUR",
            "RUB",
            "BTC",
            "ETH",
            "USDT",
            "usd",  # Should convert to uppercase
            "btc",
        ]

        for code in valid_codes:
            result = ConfigurationValidators.validate_currency_code(code)
            assert result == code.upper()
            assert len(result) >= 3
            assert len(result) <= 5
            assert result.isalpha()

    def test_validate_currency_code_invalid(self) -> None:
        """Test invalid currency code validation."""
        invalid_codes = [
            "",
            "US",  # Too short
            "USDDDD",  # Too long
            "US1",  # Contains numbers
            "US$",  # Contains symbols
            "XXX",  # Reserved code
            "XTS",  # Reserved code
        ]

        for code in invalid_codes:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_currency_code(code)

    def test_validate_currency_pair_valid(self) -> None:
        """Test valid currency pair validation."""
        valid_pairs = [
            "USD/RUB",
            "EUR/USD",
            "BTC/USDT",
            "usd/rub",  # Should convert to uppercase
            "btc/usd",
        ]

        for pair in valid_pairs:
            result = ConfigurationValidators.validate_currency_pair(pair)
            assert "/" in result
            base, quote = result.split("/")
            assert base.isupper()
            assert quote.isupper()
            assert base != quote

    def test_validate_currency_pair_invalid(self) -> None:
        """Test invalid currency pair validation."""
        invalid_pairs = [
            "",
            "USD",  # No separator
            "USD-RUB",  # Wrong separator
            "USD/RUB/EUR",  # Too many parts
            "USD/USD",  # Same currencies
            "US/RUB",  # Invalid base
            "USD/RU",  # Invalid quote
        ]

        for pair in invalid_pairs:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_currency_pair(pair)

    def test_validate_markup_rate_valid(self) -> None:
        """Test valid markup rate validation."""
        valid_rates = [0.0, 1.5, 25.0, 50.0, 2.555]  # Should round to 2.56

        for rate in valid_rates:
            result = ConfigurationValidators.validate_markup_rate(rate)
            assert result >= 0.0
            assert result <= 50.0
            # Check rounding to 2 decimal places
            assert result == round(rate, 2)

    def test_validate_markup_rate_invalid(self) -> None:
        """Test invalid markup rate validation."""
        invalid_rates = [-0.1, -10.0, 50.1, 100.0]

        for rate in invalid_rates:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_markup_rate(rate)

    def test_validate_user_id_valid(self) -> None:
        """Test valid user ID validation."""
        valid_ids = [123456789, 1234567890, 999999999]

        for user_id in valid_ids:
            result = ConfigurationValidators.validate_user_id(user_id)
            assert result == user_id
            assert result >= 100000000
            assert result <= 9999999999

    def test_validate_user_id_invalid(self) -> None:
        """Test invalid user ID validation."""
        invalid_ids = [0, -123, 99999999, 10000000000]

        for user_id in invalid_ids:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_user_id(user_id)

    def test_validate_port_valid(self) -> None:
        """Test valid port validation."""
        valid_ports = [80, 443, 8080, 65535]

        for port in valid_ports:
            result = ConfigurationValidators.validate_port(port)
            assert result == port
            assert 1 <= result <= 65535

    def test_validate_port_invalid(self) -> None:
        """Test invalid port validation."""
        invalid_ports = [0, -1, 65536, 100000]

        for port in invalid_ports:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_port(port)

    def test_validate_port_privileged_warning(self) -> None:
        """Test warning for privileged ports."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            result = ConfigurationValidators.validate_port(80)
            assert result == 80
            assert len(w) == 1
            assert "privileged port" in str(w[0].message)

    def test_validate_timeout_valid(self) -> None:
        """Test valid timeout validation."""
        valid_timeouts = [0.1, 1, 30, 300, 1.5]

        for timeout in valid_timeouts:
            result = ConfigurationValidators.validate_timeout(timeout)
            assert result == timeout
            assert result > 0
            assert result <= 300

    def test_validate_timeout_invalid(self) -> None:
        """Test invalid timeout validation."""
        invalid_timeouts = [0, -1, 301, 1000]

        for timeout in invalid_timeouts:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_timeout(timeout)

    def test_validate_cache_ttl_valid(self) -> None:
        """Test valid cache TTL validation."""
        valid_ttls = [1, 60, 3600, 86400]

        for ttl in valid_ttls:
            result = ConfigurationValidators.validate_cache_ttl(ttl)
            assert result == ttl
            assert result >= 1
            assert result <= 86400

    def test_validate_cache_ttl_invalid(self) -> None:
        """Test invalid cache TTL validation."""
        invalid_ttls = [0, -1, 86401, 100000]

        for ttl in invalid_ttls:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_cache_ttl(ttl)

    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_validate_file_path_valid(
        self, mock_makedirs: Any, mock_exists: Any
    ) -> None:
        """Test valid file path validation."""
        mock_exists.return_value = True

        valid_paths = [
            "logs/app.log",
            "/var/log/app.log",
            "data/config.json",
        ]

        for path in valid_paths:
            result = ConfigurationValidators.validate_file_path(path)
            assert result == path

    def test_validate_file_path_invalid(self) -> None:
        """Test invalid file path validation."""
        invalid_paths = [
            "",
            "logs/app<.log",  # Invalid character
            "logs/app>.log",
            "logs/app:.log",
            'logs/app".log',
            "logs/app|.log",
            "logs/app?.log",
            "logs/app*.log",
        ]

        for path in invalid_paths:
            with pytest.raises(ValueError):
                ConfigurationValidators.validate_file_path(path)

    @patch("os.path.exists")
    def test_validate_file_path_must_exist(self, mock_exists: Any) -> None:
        """Test file path validation when file must exist."""
        mock_exists.return_value = False

        with pytest.raises(ValueError) as exc_info:
            ConfigurationValidators.validate_file_path(
                "nonexistent.log", must_exist=True
            )

        assert "File does not exist" in str(exc_info.value)

    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_validate_file_path_create_directory(
        self, mock_makedirs: Any, mock_exists: Any
    ) -> None:
        """Test directory creation for file path."""
        mock_exists.side_effect = lambda path: path != "logs"

        result = ConfigurationValidators.validate_file_path("logs/app.log")
        assert result == "logs/app.log"
        mock_makedirs.assert_called_once_with("logs", exist_ok=True)


class TestBusinessRuleValidators:
    """Test cases for BusinessRuleValidators."""

    def test_validate_currency_pair_consistency_valid(self) -> None:
        """Test valid currency pair consistency."""
        currency_pairs = {
            "USD/RUB": type("CurrencyPair", (), {"is_active": True})(),
            "EUR/RUB": type("CurrencyPair", (), {"is_active": True})(),
        }

        managers = {
            123456789: type(
                "Manager",
                (),
                {"currency_pairs": {"USD/RUB", "EUR/RUB"}, "is_active": True},
            )(),
        }

        # Should not raise any exception
        BusinessRuleValidators.validate_currency_pair_consistency(
            currency_pairs, managers
        )

    def test_validate_currency_pair_consistency_invalid(self) -> None:
        """Test invalid currency pair consistency."""
        currency_pairs = {
            "USD/RUB": type("CurrencyPair", (), {"is_active": True})(),
        }

        managers = {
            123456789: type(
                "Manager",
                (),
                {
                    "currency_pairs": {"USD/RUB", "EUR/RUB"},  # EUR/RUB doesn't exist
                    "is_active": True,
                },
            )(),
        }

        with pytest.raises(ValueError) as exc_info:
            BusinessRuleValidators.validate_currency_pair_consistency(
                currency_pairs, managers
            )

        assert "non-existent currency pair" in str(exc_info.value)

    def test_validate_currency_pair_consistency_unassigned_warning(self) -> None:
        """Test warning for unassigned currency pairs."""
        currency_pairs = {
            "USD/RUB": type("CurrencyPair", (), {"is_active": True})(),
            "EUR/RUB": type("CurrencyPair", (), {"is_active": True})(),
        }

        managers = {
            123456789: type(
                "Manager",
                (),
                {
                    "currency_pairs": {"USD/RUB"},  # EUR/RUB not assigned
                    "is_active": True,
                },
            )(),
        }

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            BusinessRuleValidators.validate_currency_pair_consistency(
                currency_pairs, managers
            )

            assert len(w) == 1
            assert "without assigned managers" in str(w[0].message)
            assert "EUR/RUB" in str(w[0].message)

    def test_validate_manager_load_balance_valid(self) -> None:
        """Test valid manager load balance."""
        managers = {
            123456789: type(
                "Manager",
                (),
                {"currency_pairs": {"USD/RUB", "EUR/RUB"}, "is_active": True},
            )(),
            987654321: type(
                "Manager",
                (),
                {"currency_pairs": {"BTC/USD", "ETH/USD"}, "is_active": True},
            )(),
        }

        # Should not raise any exception
        BusinessRuleValidators.validate_manager_load_balance(managers)

    def test_validate_manager_load_balance_no_managers(self) -> None:
        """Test validation with no managers."""
        # Should not raise exception for empty managers dict
        BusinessRuleValidators.validate_manager_load_balance({})

    def test_validate_manager_load_balance_no_active_managers(self) -> None:
        """Test validation with no active managers."""
        managers = {
            123456789: type(
                "Manager", (), {"currency_pairs": {"USD/RUB"}, "is_active": False}
            )(),
        }

        with pytest.raises(ValueError) as exc_info:
            BusinessRuleValidators.validate_manager_load_balance(managers)

        assert "At least one active manager" in str(exc_info.value)

    def test_validate_manager_load_balance_no_assignments_warning(self) -> None:
        """Test warning when no pairs are assigned."""
        managers = {
            123456789: type(
                "Manager", (), {"currency_pairs": set(), "is_active": True}
            )(),
        }

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            BusinessRuleValidators.validate_manager_load_balance(managers)

            assert len(w) == 1
            assert "No currency pairs assigned" in str(w[0].message)

    def test_validate_manager_load_balance_imbalanced_warning(self) -> None:
        """Test warning for imbalanced manager load."""
        managers = {
            123456789: type(
                "Manager",
                (),
                {
                    "currency_pairs": {
                        "USD/RUB",
                        "EUR/RUB",
                        "BTC/USD",
                        "ETH/USD",
                    },  # 4 pairs
                    "is_active": True,
                },
            )(),
            987654321: type(
                "Manager",
                (),
                {"currency_pairs": {"ADA/USD"}, "is_active": True},  # 1 pair
            )(),
        }

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            BusinessRuleValidators.validate_manager_load_balance(managers)

            assert len(w) == 1
            assert "workload is imbalanced" in str(w[0].message)
            assert "4/5 pairs" in str(w[0].message)

    def test_validate_environment_consistency_production_valid(self) -> None:
        """Test valid production environment consistency."""
        # Should not raise any exception
        BusinessRuleValidators.validate_environment_consistency(
            environment="production", debug=False, log_level="INFO"
        )

    def test_validate_environment_consistency_production_debug_error(self) -> None:
        """Test error for debug mode in production."""
        with pytest.raises(ValueError) as exc_info:
            BusinessRuleValidators.validate_environment_consistency(
                environment="production", debug=True, log_level="INFO"
            )

        assert "Debug mode should not be enabled in production" in str(exc_info.value)

    def test_validate_environment_consistency_production_debug_log_warning(
        self,
    ) -> None:
        """Test warning for debug logging in production."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            BusinessRuleValidators.validate_environment_consistency(
                environment="production", debug=False, log_level="DEBUG"
            )

            assert len(w) == 1
            assert "DEBUG log level in production" in str(w[0].message)

    def test_validate_environment_consistency_development_log_warning(self) -> None:
        """Test warning for high log level in development."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            BusinessRuleValidators.validate_environment_consistency(
                environment="development", debug=True, log_level="ERROR"
            )

            assert len(w) == 1
            assert "may hide important development information" in str(w[0].message)


class TestValidatorsIntegration:
    """Integration tests for validators."""

    def test_telegram_token_and_user_id_integration(self) -> None:
        """Test integration between token and user ID validation."""
        # Valid token
        token = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        validated_token = ConfigurationValidators.validate_telegram_token(token)

        # Extract bot ID from token
        bot_id = int(validated_token.split(":")[0])

        # Validate bot ID as user ID
        validated_user_id = ConfigurationValidators.validate_user_id(bot_id)
        assert validated_user_id == bot_id

    def test_currency_pair_and_markup_integration(self) -> None:
        """Test integration between currency pair and markup validation."""
        # Validate currency pair
        pair = ConfigurationValidators.validate_currency_pair("usd/rub")
        assert pair == "USD/RUB"

        # Validate markup rate
        markup = ConfigurationValidators.validate_markup_rate(2.555)
        assert markup == 2.56

        # Both should work together in a configuration
        config_data = {"pair": pair, "markup": markup}
        assert config_data["pair"] == "USD/RUB"
        assert config_data["markup"] == 2.56
