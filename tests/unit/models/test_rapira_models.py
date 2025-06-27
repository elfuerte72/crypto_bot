"""Unit tests for Rapira API models.

This module contains comprehensive unit tests for all Rapira API data models,
including validation, properties, and edge cases.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.rapira_models import (
    CircuitBreakerState,
    RapiraApiError,
    RapiraApiResponse,
    RapiraClientConfig,
    RapiraRateData,
    RapiraRequestMetrics,
)


class TestRapiraRateData:
    """Test RapiraRateData model."""

    def test_valid_rate_data(self):
        """Test creating valid rate data."""
        data = {
            "symbol": "BTC/USDT",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "chg": 0.01,
            "change": 500.0,
            "fee": 0.002,
            "lastDayClose": 50000.0,
            "usdRate": 50500.0,
            "baseUsdRate": 1.0,
            "askPrice": 50600.0,
            "bidPrice": 50400.0,
            "baseCoinScale": 2,
            "coinScale": 6,
            "quoteCurrencyName": "Bitcoin",
            "baseCurrency": "USDT",
            "quoteCurrency": "BTC",
        }

        rate = RapiraRateData(**data)

        assert rate.symbol == "BTC/USDT"
        assert rate.open == 50000.0
        assert rate.high == 51000.0
        assert rate.low == 49000.0
        assert rate.close == 50500.0
        assert rate.chg == 0.01
        assert rate.change == 500.0
        assert rate.fee == 0.002
        assert rate.last_day_close == 50000.0
        assert rate.usd_rate == 50500.0
        assert rate.base_usd_rate == 1.0
        assert rate.ask_price == 50600.0
        assert rate.bid_price == 50400.0
        assert rate.base_coin_scale == 2
        assert rate.coin_scale == 6
        assert rate.quote_currency_name == "Bitcoin"
        assert rate.base_currency == "USDT"
        assert rate.quote_currency == "BTC"

    def test_symbol_validation(self):
        """Test symbol validation."""
        # Valid symbol
        data = {
            "symbol": "BTC/USDT",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "chg": 0.01,
            "change": 500.0,
            "fee": 0.002,
            "lastDayClose": 50000.0,
            "usdRate": 50500.0,
            "baseUsdRate": 1.0,
            "askPrice": 50600.0,
            "bidPrice": 50400.0,
            "baseCoinScale": 2,
            "coinScale": 6,
            "quoteCurrencyName": "Bitcoin",
            "baseCurrency": "USDT",
            "quoteCurrency": "BTC",
        }

        rate = RapiraRateData(**data)
        assert rate.symbol == "BTC/USDT"

        # Invalid symbol
        data["symbol"] = "BTCUSDT"  # Missing slash
        with pytest.raises(ValidationError):
            RapiraRateData(**data)

    def test_base_quote_pair_property(self):
        """Test base_quote_pair property."""
        data = {
            "symbol": "ETH/BTC",
            "open": 0.03,
            "high": 0.031,
            "low": 0.029,
            "close": 0.0305,
            "chg": 0.0167,
            "change": 0.0005,
            "fee": 0.002,
            "lastDayClose": 0.03,
            "usdRate": 1500.0,
            "baseUsdRate": 50000.0,
            "askPrice": 0.0306,
            "bidPrice": 0.0304,
            "baseCoinScale": 6,
            "coinScale": 4,
            "quoteCurrencyName": "Ethereum",
            "baseCurrency": "BTC",
            "quoteCurrency": "ETH",
        }

        rate = RapiraRateData(**data)
        base, quote = rate.base_quote_pair

        assert base == "ETH"
        assert quote == "BTC"

    def test_spread_calculation(self):
        """Test spread calculation."""
        data = {
            "symbol": "BTC/USDT",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "chg": 0.01,
            "change": 500.0,
            "fee": 0.002,
            "lastDayClose": 50000.0,
            "usdRate": 50500.0,
            "baseUsdRate": 1.0,
            "askPrice": 50600.0,
            "bidPrice": 50400.0,
            "baseCoinScale": 2,
            "coinScale": 6,
            "quoteCurrencyName": "Bitcoin",
            "baseCurrency": "USDT",
            "quoteCurrency": "BTC",
        }

        rate = RapiraRateData(**data)

        assert rate.spread == 200.0  # 50600 - 50400
        assert abs(rate.spread_percentage - 0.395) < 0.001  # (200/50600) * 100

    def test_change_properties(self):
        """Test change-related properties."""
        # Positive change
        data = {
            "symbol": "BTC/USDT",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "chg": 0.01,
            "change": 500.0,
            "fee": 0.002,
            "lastDayClose": 50000.0,
            "usdRate": 50500.0,
            "baseUsdRate": 1.0,
            "askPrice": 50600.0,
            "bidPrice": 50400.0,
            "baseCoinScale": 2,
            "coinScale": 6,
            "quoteCurrencyName": "Bitcoin",
            "baseCurrency": "USDT",
            "quoteCurrency": "BTC",
        }

        rate = RapiraRateData(**data)

        assert rate.change_percentage == 1.0  # 0.01 * 100
        assert rate.is_positive_change is True

        # Negative change
        data["change"] = -500.0
        data["chg"] = -0.01
        rate = RapiraRateData(**data)

        assert rate.change_percentage == -1.0
        assert rate.is_positive_change is False

    def test_zero_ask_price_spread(self):
        """Test spread calculation with zero ask price."""
        data = {
            "symbol": "BTC/USDT",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "chg": 0.01,
            "change": 500.0,
            "fee": 0.002,
            "lastDayClose": 50000.0,
            "usdRate": 50500.0,
            "baseUsdRate": 1.0,
            "askPrice": 0.0,
            "bidPrice": 50400.0,
            "baseCoinScale": 2,
            "coinScale": 6,
            "quoteCurrencyName": "Bitcoin",
            "baseCurrency": "USDT",
            "quoteCurrency": "BTC",
        }

        rate = RapiraRateData(**data)

        assert rate.spread == -50400.0
        assert rate.spread_percentage == 0.0  # Should handle division by zero


class TestRapiraApiResponse:
    """Test RapiraApiResponse model."""

    def test_valid_response(self):
        """Test creating valid API response."""
        data = {
            "data": [
                {
                    "symbol": "BTC/USDT",
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "chg": 0.01,
                    "change": 500.0,
                    "fee": 0.002,
                    "lastDayClose": 50000.0,
                    "usdRate": 50500.0,
                    "baseUsdRate": 1.0,
                    "askPrice": 50600.0,
                    "bidPrice": 50400.0,
                    "baseCoinScale": 2,
                    "coinScale": 6,
                    "quoteCurrencyName": "Bitcoin",
                    "baseCurrency": "USDT",
                    "quoteCurrency": "BTC",
                }
            ],
            "code": 0,
            "message": "SUCCESS",
            "totalPage": None,
            "totalElement": None,
            "isWorking": 1,
        }

        response = RapiraApiResponse(**data)

        assert len(response.data) == 1
        assert response.code == 0
        assert response.message == "SUCCESS"
        assert response.total_page is None
        assert response.total_element is None
        assert response.is_working == 1

    def test_response_properties(self):
        """Test response properties."""
        data = {
            "data": [],
            "code": 0,
            "message": "SUCCESS",
            "totalPage": None,
            "totalElement": None,
            "isWorking": 1,
        }

        response = RapiraApiResponse(**data)

        assert response.is_success is True
        assert response.is_api_working is True

    def test_error_code_validation(self):
        """Test error code validation."""
        data = {
            "data": [],
            "code": 1,  # Error code
            "message": "ERROR",
            "totalPage": None,
            "totalElement": None,
            "isWorking": 1,
        }

        with pytest.raises(ValidationError):
            RapiraApiResponse(**data)

    def test_get_rate_by_symbol(self):
        """Test getting rate by symbol."""
        data = {
            "data": [
                {
                    "symbol": "BTC/USDT",
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "chg": 0.01,
                    "change": 500.0,
                    "fee": 0.002,
                    "lastDayClose": 50000.0,
                    "usdRate": 50500.0,
                    "baseUsdRate": 1.0,
                    "askPrice": 50600.0,
                    "bidPrice": 50400.0,
                    "baseCoinScale": 2,
                    "coinScale": 6,
                    "quoteCurrencyName": "Bitcoin",
                    "baseCurrency": "USDT",
                    "quoteCurrency": "BTC",
                },
                {
                    "symbol": "ETH/USDT",
                    "open": 3000.0,
                    "high": 3100.0,
                    "low": 2900.0,
                    "close": 3050.0,
                    "chg": 0.0167,
                    "change": 50.0,
                    "fee": 0.002,
                    "lastDayClose": 3000.0,
                    "usdRate": 3050.0,
                    "baseUsdRate": 1.0,
                    "askPrice": 3060.0,
                    "bidPrice": 3040.0,
                    "baseCoinScale": 2,
                    "coinScale": 4,
                    "quoteCurrencyName": "Ethereum",
                    "baseCurrency": "USDT",
                    "quoteCurrency": "ETH",
                },
            ],
            "code": 0,
            "message": "SUCCESS",
            "totalPage": None,
            "totalElement": None,
            "isWorking": 1,
        }

        response = RapiraApiResponse(**data)

        # Found symbol
        btc_rate = response.get_rate_by_symbol("BTC/USDT")
        assert btc_rate is not None
        assert btc_rate.symbol == "BTC/USDT"

        # Not found symbol
        not_found = response.get_rate_by_symbol("DOGE/USDT")
        assert not_found is None

    def test_get_supported_symbols(self):
        """Test getting supported symbols."""
        data = {
            "data": [
                {
                    "symbol": "BTC/USDT",
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "chg": 0.01,
                    "change": 500.0,
                    "fee": 0.002,
                    "lastDayClose": 50000.0,
                    "usdRate": 50500.0,
                    "baseUsdRate": 1.0,
                    "askPrice": 50600.0,
                    "bidPrice": 50400.0,
                    "baseCoinScale": 2,
                    "coinScale": 6,
                    "quoteCurrencyName": "Bitcoin",
                    "baseCurrency": "USDT",
                    "quoteCurrency": "BTC",
                },
                {
                    "symbol": "ETH/USDT",
                    "open": 3000.0,
                    "high": 3100.0,
                    "low": 2900.0,
                    "close": 3050.0,
                    "chg": 0.0167,
                    "change": 50.0,
                    "fee": 0.002,
                    "lastDayClose": 3000.0,
                    "usdRate": 3050.0,
                    "baseUsdRate": 1.0,
                    "askPrice": 3060.0,
                    "bidPrice": 3040.0,
                    "baseCoinScale": 2,
                    "coinScale": 4,
                    "quoteCurrencyName": "Ethereum",
                    "baseCurrency": "USDT",
                    "quoteCurrency": "ETH",
                },
            ],
            "code": 0,
            "message": "SUCCESS",
            "totalPage": None,
            "totalElement": None,
            "isWorking": 1,
        }

        response = RapiraApiResponse(**data)
        symbols = response.get_supported_symbols()

        assert len(symbols) == 2
        assert "BTC/USDT" in symbols
        assert "ETH/USDT" in symbols


class TestRapiraApiError:
    """Test RapiraApiError model."""

    def test_valid_error(self):
        """Test creating valid error."""
        error = RapiraApiError(
            code=500,
            message="Internal server error",
            details="Database connection failed",
        )

        assert error.code == 500
        assert error.message == "Internal server error"
        assert error.details == "Database connection failed"
        assert isinstance(error.timestamp, datetime)

    def test_error_properties(self):
        """Test error classification properties."""
        # Client error
        client_error = RapiraApiError(code=400, message="Bad request")
        assert client_error.is_client_error is True
        assert client_error.is_server_error is False
        assert client_error.is_rate_limit_error is False

        # Server error
        server_error = RapiraApiError(code=500, message="Internal error")
        assert server_error.is_client_error is False
        assert server_error.is_server_error is True
        assert server_error.is_rate_limit_error is False

        # Rate limit error
        rate_limit_error = RapiraApiError(code=429, message="Rate limit exceeded")
        assert rate_limit_error.is_client_error is True  # 429 is in 4xx range
        assert rate_limit_error.is_server_error is False
        assert rate_limit_error.is_rate_limit_error is True

    def test_default_timestamp(self):
        """Test default timestamp generation."""
        error = RapiraApiError(code=500, message="Test error")

        assert error.timestamp is not None
        assert isinstance(error.timestamp, datetime)

        # Should be recent
        time_diff = datetime.now() - error.timestamp
        assert time_diff.total_seconds() < 1.0


class TestRapiraClientConfig:
    """Test RapiraClientConfig model."""

    def test_valid_config(self):
        """Test creating valid configuration."""
        config = RapiraClientConfig(
            base_url="https://api.rapira.net",
            timeout=30,
            max_retries=3,
            retry_delay=1.0,
            backoff_factor=2.0,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60,
        )

        assert config.base_url == "https://api.rapira.net"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.backoff_factor == 2.0
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout == 60

    def test_default_values(self):
        """Test default configuration values."""
        config = RapiraClientConfig(base_url="https://api.rapira.net")

        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.backoff_factor == 2.0
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout == 60

    def test_base_url_validation(self):
        """Test base URL validation."""
        # Valid URLs
        config1 = RapiraClientConfig(base_url="https://api.rapira.net")
        assert config1.base_url == "https://api.rapira.net"

        config2 = RapiraClientConfig(base_url="http://localhost:8000/")
        assert config2.base_url == "http://localhost:8000"  # Trailing slash removed

        # Invalid URL
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="invalid-url")

    def test_parameter_validation(self):
        """Test parameter validation ranges."""
        # Valid parameters
        config = RapiraClientConfig(
            base_url="https://api.rapira.net",
            timeout=30,
            max_retries=5,
            retry_delay=2.0,
            backoff_factor=1.5,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=120,
        )
        assert config.timeout == 30
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.backoff_factor == 1.5
        assert config.circuit_breaker_threshold == 3
        assert config.circuit_breaker_timeout == 120

        # Invalid timeout (too low)
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", timeout=2)

        # Invalid timeout (too high)
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", timeout=200)

        # Invalid max_retries (too high)
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", max_retries=15)

        # Invalid retry_delay (too low)
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", retry_delay=0.05)

        # Invalid backoff_factor (too low)
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", backoff_factor=0.5)


class TestCircuitBreakerState:
    """Test CircuitBreakerState model."""

    def test_initial_state(self):
        """Test initial state."""
        cb = CircuitBreakerState()

        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "closed"
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.is_half_open is False

    def test_record_failure(self):
        """Test recording failures."""
        cb = CircuitBreakerState()

        cb.record_failure()

        assert cb.failure_count == 1
        assert cb.last_failure_time is not None
        assert isinstance(cb.last_failure_time, datetime)

        # Record another failure
        cb.record_failure()
        assert cb.failure_count == 2

    def test_state_transitions(self):
        """Test state transitions."""
        cb = CircuitBreakerState()

        # Open circuit
        cb.open_circuit()
        assert cb.state == "open"
        assert cb.is_open is True
        assert cb.is_closed is False
        assert cb.is_half_open is False

        # Half-open circuit
        cb.half_open_circuit()
        assert cb.state == "half_open"
        assert cb.is_half_open is True
        assert cb.is_open is False
        assert cb.is_closed is False

        # Reset circuit
        cb.reset()
        assert cb.state == "closed"
        assert cb.is_closed is True
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestRapiraRequestMetrics:
    """Test RapiraRequestMetrics model."""

    def test_initial_metrics(self):
        """Test initial metrics."""
        metrics = RapiraRequestMetrics()

        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.avg_response_time == 0.0
        assert metrics.last_request_time is None
        assert metrics.last_success_time is None
        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 0.0

    def test_record_successful_request(self):
        """Test recording successful request."""
        metrics = RapiraRequestMetrics()

        metrics.record_request(True, 0.5)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.avg_response_time == 0.5
        assert metrics.success_rate == 100.0
        assert metrics.failure_rate == 0.0
        assert metrics.last_request_time is not None
        assert metrics.last_success_time is not None

    def test_record_failed_request(self):
        """Test recording failed request."""
        metrics = RapiraRequestMetrics()

        metrics.record_request(False, 1.0)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.avg_response_time == 1.0
        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 100.0
        assert metrics.last_request_time is not None
        assert metrics.last_success_time is None

    def test_mixed_requests(self):
        """Test recording mixed successful and failed requests."""
        metrics = RapiraRequestMetrics()

        # 2 successful, 1 failed
        metrics.record_request(True, 0.5)
        metrics.record_request(True, 1.0)
        metrics.record_request(False, 2.0)

        assert metrics.total_requests == 3
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 1
        assert abs(metrics.avg_response_time - 1.167) < 0.01  # (0.5 + 1.0 + 2.0) / 3
        assert abs(metrics.success_rate - 66.67) < 0.01  # 2/3 * 100
        assert abs(metrics.failure_rate - 33.33) < 0.01  # 1/3 * 100

    def test_average_response_time_calculation(self):
        """Test average response time calculation."""
        metrics = RapiraRequestMetrics()

        # First request
        metrics.record_request(True, 1.0)
        assert metrics.avg_response_time == 1.0

        # Second request
        metrics.record_request(True, 2.0)
        assert metrics.avg_response_time == 1.5  # (1.0 + 2.0) / 2

        # Third request
        metrics.record_request(False, 0.0)
        assert abs(metrics.avg_response_time - 1.0) < 0.01  # (1.0 + 2.0 + 0.0) / 3

    def test_success_failure_rates_edge_cases(self):
        """Test success/failure rate calculations with edge cases."""
        metrics = RapiraRequestMetrics()

        # No requests
        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 0.0

        # Only successful requests
        metrics.record_request(True, 1.0)
        metrics.record_request(True, 1.0)
        assert metrics.success_rate == 100.0
        assert metrics.failure_rate == 0.0

        # Only failed requests
        metrics = RapiraRequestMetrics()
        metrics.record_request(False, 1.0)
        metrics.record_request(False, 1.0)
        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 100.0
