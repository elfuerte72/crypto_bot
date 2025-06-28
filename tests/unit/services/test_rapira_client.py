"""Unit tests for Rapira API client.

This module contains comprehensive unit tests for the Rapira API client,
including testing of retry logic, circuit breaker, error handling, and metrics.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from models.rapira_models import (
    CircuitBreakerState,
    RapiraApiResponse,
    RapiraClientConfig,
    RapiraRateData,
    RapiraRequestMetrics,
)
from services.rapira_client import (
    RapiraApiClient,
    RapiraApiException,
    RapiraCircuitBreakerError,
    RapiraClientError,
    RapiraClientFactory,
    RapiraRateLimitError,
    RapiraServerError,
)


class TestRapiraClientConfig:
    """Test RapiraClientConfig model."""

    def test_valid_config(self):
        """Test valid configuration creation."""
        config = RapiraClientConfig(
            base_url="https://api.rapira.net",
            timeout=30,
            max_retries=3,
            retry_delay=1.0,
            backoff_factor=2.0,
        )

        assert config.base_url == "https://api.rapira.net"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.backoff_factor == 2.0

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
        """Test parameter validation."""
        # Valid parameters
        config = RapiraClientConfig(
            base_url="https://api.rapira.net",
            timeout=30,
            max_retries=5,
            retry_delay=2.0,
            backoff_factor=1.5,
        )
        assert config.timeout == 30
        assert config.max_retries == 5

        # Invalid timeout
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", timeout=2)

        # Invalid max_retries
        with pytest.raises(ValidationError):
            RapiraClientConfig(base_url="https://api.rapira.net", max_retries=15)


class TestCircuitBreakerState:
    """Test CircuitBreakerState model."""

    def test_initial_state(self):
        """Test initial circuit breaker state."""
        cb = CircuitBreakerState()
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "closed"
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open

    def test_record_failure(self):
        """Test recording failures."""
        cb = CircuitBreakerState()
        cb.record_failure()

        assert cb.failure_count == 1
        assert cb.last_failure_time is not None
        assert isinstance(cb.last_failure_time, datetime)

    def test_state_transitions(self):
        """Test circuit breaker state transitions."""
        cb = CircuitBreakerState()

        # Open circuit
        cb.open_circuit()
        assert cb.is_open
        assert cb.state == "open"

        # Half-open circuit
        cb.half_open_circuit()
        assert cb.is_half_open
        assert cb.state == "half_open"

        # Reset circuit
        cb.reset()
        assert cb.is_closed
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestRapiraRequestMetrics:
    """Test RapiraRequestMetrics model."""

    def test_initial_metrics(self):
        """Test initial metrics state."""
        metrics = RapiraRequestMetrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.avg_response_time == 0.0
        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 0.0

    def test_record_successful_request(self):
        """Test recording successful requests."""
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
        """Test recording failed requests."""
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

    def test_average_response_time_calculation(self):
        """Test average response time calculation."""
        metrics = RapiraRequestMetrics()

        # First request: 1.0s
        metrics.record_request(True, 1.0)
        assert metrics.avg_response_time == 1.0

        # Second request: 2.0s, average should be 1.5s
        metrics.record_request(True, 2.0)
        assert metrics.avg_response_time == 1.5

        # Third request: 0.0s, average should be 1.0s
        metrics.record_request(False, 0.0)
        assert metrics.avg_response_time == 1.0


@pytest.fixture
def mock_response_data():
    """Mock Rapira API response data."""
    return {
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


@pytest.fixture
def rapira_config():
    """Rapira client configuration fixture."""
    return RapiraClientConfig(
        base_url="https://api.rapira.net",
        timeout=30,
        max_retries=3,
        retry_delay=0.1,  # Shorter delay for tests
        backoff_factor=2.0,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout=10,  # Minimum allowed value
    )


@pytest.fixture
def rapira_client(rapira_config):
    """Rapira client fixture."""
    return RapiraApiClient(rapira_config)


class TestRapiraApiClient:
    """Test RapiraApiClient class."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, rapira_client):
        """Test client initialization."""
        assert rapira_client.config.base_url == "https://api.rapira.net"
        assert rapira_client.circuit_breaker.is_closed
        assert rapira_client.metrics.total_requests == 0
        assert rapira_client._client is None

    @pytest.mark.asyncio
    async def test_context_manager(self, rapira_client):
        """Test async context manager."""
        async with rapira_client as client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

        # Client should be closed after context exit
        assert rapira_client._client is None

    @pytest.mark.asyncio
    async def test_successful_request(self, rapira_client, mock_response_data):
        """Test successful API request."""
        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.return_value = mock_response_data

            response = await rapira_client.get_market_rates()

            assert isinstance(response, RapiraApiResponse)
            assert len(response.data) == 1
            assert response.data[0].symbol == "BTC/USDT"
            assert response.is_success
            assert response.is_api_working

    @pytest.mark.asyncio
    async def test_get_rate_by_symbol(self, rapira_client, mock_response_data):
        """Test getting rate by symbol."""
        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.return_value = mock_response_data

            rate = await rapira_client.get_rate_by_symbol("BTC/USDT")

            assert rate is not None
            assert isinstance(rate, RapiraRateData)
            assert rate.symbol == "BTC/USDT"
            assert rate.close == 50500.0

    @pytest.mark.asyncio
    async def test_get_rate_by_symbol_not_found(
        self, rapira_client, mock_response_data
    ):
        """Test getting rate for non-existent symbol."""
        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.return_value = mock_response_data

            rate = await rapira_client.get_rate_by_symbol("ETH/BTC")

            assert rate is None

    @pytest.mark.asyncio
    async def test_get_supported_symbols(self, rapira_client, mock_response_data):
        """Test getting supported symbols."""
        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.return_value = mock_response_data

            symbols = await rapira_client.get_supported_symbols()

            assert symbols == ["BTC/USDT"]

    @pytest.mark.asyncio
    async def test_health_check_success(self, rapira_client, mock_response_data):
        """Test successful health check."""
        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.return_value = mock_response_data

            is_healthy = await rapira_client.health_check()

            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, rapira_client):
        """Test failed health check."""
        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.side_effect = RapiraApiException("Connection failed")

            is_healthy = await rapira_client.health_check()

            assert is_healthy is False

    def test_calculate_retry_delay(self, rapira_client):
        """Test retry delay calculation."""
        # First retry: 0.1 * 2^0 = 0.1
        assert rapira_client._calculate_retry_delay(0) == 0.1

        # Second retry: 0.1 * 2^1 = 0.2
        assert rapira_client._calculate_retry_delay(1) == 0.2

        # Third retry: 0.1 * 2^2 = 0.4
        assert rapira_client._calculate_retry_delay(2) == 0.4

    def test_circuit_breaker_check_closed(self, rapira_client):
        """Test circuit breaker check when closed."""
        # Should not raise exception
        rapira_client._check_circuit_breaker()

    def test_circuit_breaker_check_open(self, rapira_client):
        """Test circuit breaker check when open."""
        rapira_client.circuit_breaker.open_circuit()
        rapira_client.circuit_breaker.record_failure()

        with pytest.raises(RapiraCircuitBreakerError):
            rapira_client._check_circuit_breaker()

    def test_circuit_breaker_check_half_open_timeout(self, rapira_client):
        """Test circuit breaker transitions to half-open after timeout."""
        # Open circuit and set old failure time
        rapira_client.circuit_breaker.open_circuit()
        rapira_client.circuit_breaker.last_failure_time = datetime.now() - timedelta(
            seconds=10
        )

        # Should transition to half-open
        rapira_client._check_circuit_breaker()
        assert rapira_client.circuit_breaker.is_half_open

    def test_circuit_breaker_success_handling(self, rapira_client):
        """Test circuit breaker success handling."""
        # Set to half-open state
        rapira_client.circuit_breaker.half_open_circuit()

        # Handle success
        rapira_client._handle_circuit_breaker_success()

        # Should be reset to closed
        assert rapira_client.circuit_breaker.is_closed
        assert rapira_client.circuit_breaker.failure_count == 0

    def test_circuit_breaker_failure_handling(self, rapira_client):
        """Test circuit breaker failure handling."""
        # Record failures up to threshold
        for _ in range(rapira_client.config.circuit_breaker_threshold):
            rapira_client._handle_circuit_breaker_failure()

        # Should be open now
        assert rapira_client.circuit_breaker.is_open

    def test_reset_circuit_breaker(self, rapira_client):
        """Test manual circuit breaker reset."""
        rapira_client.circuit_breaker.open_circuit()
        rapira_client.circuit_breaker.record_failure()

        rapira_client.reset_circuit_breaker()

        assert rapira_client.circuit_breaker.is_closed
        assert rapira_client.circuit_breaker.failure_count == 0

    def test_reset_metrics(self, rapira_client):
        """Test metrics reset."""
        rapira_client.metrics.record_request(True, 1.0)
        assert rapira_client.metrics.total_requests == 1

        rapira_client.reset_metrics()

        assert rapira_client.metrics.total_requests == 0
        assert rapira_client.metrics.successful_requests == 0

    def test_get_metrics(self, rapira_client):
        """Test getting metrics."""
        metrics = rapira_client.get_metrics()
        assert isinstance(metrics, RapiraRequestMetrics)
        assert metrics.total_requests == 0

    def test_get_circuit_breaker_state(self, rapira_client):
        """Test getting circuit breaker state."""
        state = rapira_client.get_circuit_breaker_state()
        assert isinstance(state, CircuitBreakerState)
        assert state.is_closed


class TestRapiraApiClientHttpErrors:
    """Test HTTP error handling in RapiraApiClient."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, rapira_client):
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch.object(rapira_client, "_ensure_client"):
            with patch.object(rapira_client, "_client") as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                with pytest.raises(RapiraRateLimitError) as exc_info:
                    await rapira_client._make_request("/test")

                assert exc_info.value.error_code == 429
                assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_client_error(self, rapira_client):
        """Test client error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with patch.object(rapira_client, "_ensure_client"):
            with patch.object(rapira_client, "_client") as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                with pytest.raises(RapiraClientError) as exc_info:
                    await rapira_client._make_request("/test")

                assert exc_info.value.error_code == 400
                assert "Client error: 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_server_error_with_retry(self, rapira_client):
        """Test server error with retry logic."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch.object(rapira_client, "_ensure_client"):
            with patch.object(rapira_client, "_client") as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                with patch(
                    "asyncio.sleep"
                ) as mock_sleep:  # Mock sleep to speed up test
                    with pytest.raises(RapiraServerError) as exc_info:
                        await rapira_client._make_request("/test")

                    assert exc_info.value.error_code == 500
                    assert "Server error: 500" in str(exc_info.value)

                    # Should have retried
                    assert (
                        mock_client.get.call_count
                        == rapira_client.config.max_retries + 1
                    )
                    assert mock_sleep.call_count == rapira_client.config.max_retries

    @pytest.mark.asyncio
    async def test_timeout_error_with_retry(self, rapira_client):
        """Test timeout error with retry logic."""
        with patch.object(rapira_client, "_ensure_client"):
            with patch.object(rapira_client, "_client") as mock_client:
                mock_client.get = AsyncMock(
                    side_effect=httpx.TimeoutException("Request timeout")
                )

                with patch("asyncio.sleep") as mock_sleep:
                    with pytest.raises(RapiraApiException) as exc_info:
                        await rapira_client._make_request("/test")

                    assert "Request timeout" in str(exc_info.value)
                    assert (
                        mock_client.get.call_count
                        == rapira_client.config.max_retries + 1
                    )
                    assert mock_sleep.call_count == rapira_client.config.max_retries

    @pytest.mark.asyncio
    async def test_network_error_with_retry(self, rapira_client):
        """Test network error with retry logic."""
        with patch.object(rapira_client, "_ensure_client"):
            with patch.object(rapira_client, "_client") as mock_client:
                mock_client.get = AsyncMock(
                    side_effect=httpx.NetworkError("Network unreachable")
                )

                with patch("asyncio.sleep") as mock_sleep:
                    with pytest.raises(RapiraApiException) as exc_info:
                        await rapira_client._make_request("/test")

                    assert "Network error" in str(exc_info.value)
                    assert (
                        mock_client.get.call_count
                        == rapira_client.config.max_retries + 1
                    )
                    assert mock_sleep.call_count == rapira_client.config.max_retries

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, rapira_client):
        """Test invalid JSON response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid response"

        with patch.object(rapira_client, "_ensure_client"):
            with patch.object(rapira_client, "_client") as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                with pytest.raises(RapiraApiException) as exc_info:
                    await rapira_client._make_request("/test")

                assert "Invalid JSON response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, rapira_client):
        """Test validation error handling."""
        invalid_data = {"invalid": "data"}

        with patch.object(rapira_client, "_make_request") as mock_request:
            mock_request.return_value = invalid_data

            with pytest.raises(RapiraApiException) as exc_info:
                await rapira_client.get_market_rates()

            assert "Invalid API response format" in str(exc_info.value)


class TestRapiraClientFactory:
    """Test RapiraClientFactory class."""

    def test_create_client(self):
        """Test creating client with factory."""
        client = RapiraClientFactory.create_client(
            base_url="https://api.rapira.net",
            timeout=60,
            max_retries=5,
        )

        assert isinstance(client, RapiraApiClient)
        assert client.config.base_url == "https://api.rapira.net"
        assert client.config.timeout == 60
        assert client.config.max_retries == 5

    def test_create_from_settings(self):
        """Test creating client from settings."""
        # Mock settings object
        mock_settings = MagicMock()
        mock_settings.rapira_api.base_url = "https://api.rapira.net"
        mock_settings.rapira_api.timeout = 30
        mock_settings.rapira_api.max_retries = 3
        mock_settings.rapira_api.retry_delay = 1.0
        mock_settings.rapira_api.backoff_factor = 2.0

        # Mock getattr to return default values for circuit breaker settings
        with patch("services.rapira_client.getattr") as mock_getattr:

            def getattr_side_effect(obj, attr, default):
                if attr == "circuit_breaker_threshold":
                    return 5
                elif attr == "circuit_breaker_timeout":
                    return 10  # Must be >= 10 according to validation
                return default

            mock_getattr.side_effect = getattr_side_effect

            client = RapiraClientFactory.create_from_settings(mock_settings)

            assert isinstance(client, RapiraApiClient)
            assert client.config.base_url == "https://api.rapira.net"
            assert client.config.timeout == 30
            assert client.config.max_retries == 3


class TestRapiraApiExceptions:
    """Test custom exception classes."""

    def test_rapira_api_exception(self):
        """Test base exception."""
        exc = RapiraApiException("Test error", error_code=500, details="Test details")

        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.error_code == 500
        assert exc.details == "Test details"

    def test_rapira_client_error(self):
        """Test client error exception."""
        exc = RapiraClientError("Client error", error_code=400)

        assert str(exc) == "Client error"
        assert exc.error_code == 400
        assert isinstance(exc, RapiraApiException)

    def test_rapira_server_error(self):
        """Test server error exception."""
        exc = RapiraServerError("Server error", error_code=500)

        assert str(exc) == "Server error"
        assert exc.error_code == 500
        assert isinstance(exc, RapiraApiException)

    def test_rapira_rate_limit_error(self):
        """Test rate limit error exception."""
        exc = RapiraRateLimitError("Rate limit", error_code=429)

        assert str(exc) == "Rate limit"
        assert exc.error_code == 429
        assert isinstance(exc, RapiraApiException)

    def test_rapira_circuit_breaker_error(self):
        """Test circuit breaker error exception."""
        exc = RapiraCircuitBreakerError("Circuit breaker open")

        assert str(exc) == "Circuit breaker open"
        assert isinstance(exc, RapiraApiException)


@pytest.mark.asyncio
async def test_integration_with_real_api():
    """Integration test with real API (optional, can be skipped)."""
    pytest.skip("Integration test - requires real API access")

    config = RapiraClientConfig(
        base_url="https://api.rapira.net",
        timeout=10,
        max_retries=1,
    )

    async with RapiraApiClient(config) as client:
        try:
            response = await client.get_market_rates()
            assert response.is_success
            assert len(response.data) > 0

            # Test specific symbol
            btc_rate = await client.get_rate_by_symbol("BTC/USDT")
            if btc_rate:
                assert btc_rate.symbol == "BTC/USDT"
                assert btc_rate.close > 0

            # Test health check
            is_healthy = await client.health_check()
            assert is_healthy is True

        except Exception as e:
            pytest.skip(f"Real API test failed: {e}")
