"""Rapira API client implementation.

This module provides an asynchronous HTTP client for interacting with the Rapira API,
including retry logic, circuit breaker pattern, error handling, and metrics collection.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError

from ..models.rapira_models import (
    CircuitBreakerState,
    RapiraApiResponse,
    RapiraClientConfig,
    RapiraRateData,
    RapiraRequestMetrics,
)

logger = logging.getLogger(__name__)


class RapiraApiException(Exception):
    """Base exception for Rapira API errors."""

    def __init__(
        self, message: str, error_code: int | None = None, details: str | None = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details


class RapiraClientError(RapiraApiException):
    """Client-side error (4xx)."""

    pass


class RapiraServerError(RapiraApiException):
    """Server-side error (5xx)."""

    pass


class RapiraRateLimitError(RapiraApiException):
    """Rate limiting error (429)."""

    pass


class RapiraCircuitBreakerError(RapiraApiException):
    """Circuit breaker is open."""

    pass


class RapiraApiClient:
    """Asynchronous Rapira API client with advanced error handling and resilience patterns."""

    def __init__(self, config: RapiraClientConfig):
        """Initialize the Rapira API client.

        Args:
            config: Client configuration
        """
        self.config = config
        self.circuit_breaker = CircuitBreakerState()
        self.metrics = RapiraRequestMetrics()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> RapiraApiClient:
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers={
                    "User-Agent": "CryptoBot/1.0.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                follow_redirects=True,
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _check_circuit_breaker(self) -> None:
        """Check circuit breaker state and raise exception if open."""
        if not self.circuit_breaker.is_open:
            return

        # Check if we should try half-open state
        if (
            self.circuit_breaker.last_failure_time
            and datetime.now() - self.circuit_breaker.last_failure_time
            > timedelta(seconds=self.config.circuit_breaker_timeout)
        ):
            self.circuit_breaker.half_open_circuit()
            logger.info("Circuit breaker moved to half-open state")
            return

        raise RapiraCircuitBreakerError(
            f"Circuit breaker is open. Last failure: {self.circuit_breaker.last_failure_time}"
        )

    def _handle_circuit_breaker_success(self) -> None:
        """Handle successful request for circuit breaker."""
        if self.circuit_breaker.is_half_open:
            self.circuit_breaker.reset()
            logger.info(
                "Circuit breaker reset to closed state after successful request"
            )

    def _handle_circuit_breaker_failure(self) -> None:
        """Handle failed request for circuit breaker."""
        self.circuit_breaker.record_failure()

        if self.circuit_breaker.failure_count >= self.config.circuit_breaker_threshold:
            self.circuit_breaker.open_circuit()
            logger.warning(
                f"Circuit breaker opened after {self.circuit_breaker.failure_count} failures"
            )

    async def _make_request(self, endpoint: str) -> dict[str, Any]:
        """Make HTTP request with retry logic and error handling.

        Args:
            endpoint: API endpoint path

        Returns:
            Response data as dictionary

        Raises:
            RapiraApiException: For various API errors
        """
        await self._ensure_client()
        self._check_circuit_breaker()

        url = f"{self.config.base_url}{endpoint}"
        last_exception: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            start_time = datetime.now()

            try:
                logger.debug(f"Making request to {url} (attempt {attempt + 1})")

                response = await self._client.get(url)  # type: ignore
                response_time = (datetime.now() - start_time).total_seconds()

                # Handle HTTP errors
                if response.status_code == 429:
                    error = RapiraRateLimitError(
                        "Rate limit exceeded", error_code=response.status_code
                    )
                    self._handle_circuit_breaker_failure()
                    self.metrics.record_request(False, response_time)
                    raise error

                if 400 <= response.status_code < 500:
                    error = RapiraClientError(
                        f"Client error: {response.status_code}",
                        error_code=response.status_code,
                        details=response.text,
                    )
                    self._handle_circuit_breaker_failure()
                    self.metrics.record_request(False, response_time)
                    raise error

                if 500 <= response.status_code < 600:
                    error = RapiraServerError(
                        f"Server error: {response.status_code}",
                        error_code=response.status_code,
                        details=response.text,
                    )
                    self._handle_circuit_breaker_failure()
                    self.metrics.record_request(False, response_time)

                    # Retry on server errors
                    if attempt < self.config.max_retries:
                        delay = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Server error {response.status_code}, retrying in {delay}s"
                        )
                        await asyncio.sleep(delay)
                        continue

                    raise error

                # Parse JSON response
                try:
                    data = response.json()
                except ValueError as e:
                    error = RapiraApiException(
                        f"Invalid JSON response: {e}",
                        details=response.text[:500],
                    )
                    self._handle_circuit_breaker_failure()
                    self.metrics.record_request(False, response_time)
                    raise error

                # Success
                self._handle_circuit_breaker_success()
                self.metrics.record_request(True, response_time)
                logger.debug(f"Request successful in {response_time:.2f}s")
                return data

            except httpx.TimeoutException as e:
                response_time = (datetime.now() - start_time).total_seconds()
                last_exception = RapiraApiException(f"Request timeout: {e}")
                self._handle_circuit_breaker_failure()
                self.metrics.record_request(False, response_time)

                if attempt < self.config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Request timeout, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue

            except httpx.NetworkError as e:
                response_time = (datetime.now() - start_time).total_seconds()
                last_exception = RapiraApiException(f"Network error: {e}")
                self._handle_circuit_breaker_failure()
                self.metrics.record_request(False, response_time)

                if attempt < self.config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Network error, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue

            except (RapiraRateLimitError, RapiraClientError, RapiraServerError):
                # Re-raise our custom exceptions
                raise
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                last_exception = RapiraApiException(f"Unexpected error: {e}")
                self._handle_circuit_breaker_failure()
                self.metrics.record_request(False, response_time)
                break

        # All retries exhausted
        if last_exception:
            raise last_exception

        raise RapiraApiException("All retry attempts exhausted")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        return self.config.retry_delay * (self.config.backoff_factor**attempt)

    async def get_market_rates(self) -> RapiraApiResponse:
        """Get all market rates from Rapira API.

        Returns:
            Parsed API response with rate data

        Raises:
            RapiraApiException: For various API errors
            ValidationError: For response validation errors
        """
        try:
            data = await self._make_request("/open/market/rates")
            response = RapiraApiResponse(**data)

            logger.info(f"Retrieved {len(response.data)} market rates")
            return response

        except ValidationError as e:
            logger.error(f"Response validation error: {e}")
            raise RapiraApiException(f"Invalid API response format: {e}")

    async def get_rate_by_symbol(self, symbol: str) -> RapiraRateData | None:
        """Get rate data for a specific symbol.

        Args:
            symbol: Currency pair symbol (e.g., 'BTC/USDT')

        Returns:
            Rate data or None if not found
        """
        response = await self.get_market_rates()
        return response.get_rate_by_symbol(symbol)

    async def get_supported_symbols(self) -> list[str]:
        """Get list of all supported trading symbols.

        Returns:
            List of supported symbols
        """
        response = await self.get_market_rates()
        return response.get_supported_symbols()

    async def health_check(self) -> bool:
        """Perform health check on the API.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = await self.get_market_rates()
            return response.is_api_working and response.is_success
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def get_metrics(self) -> RapiraRequestMetrics:
        """Get client metrics.

        Returns:
            Current metrics
        """
        return self.metrics

    def get_circuit_breaker_state(self) -> CircuitBreakerState:
        """Get circuit breaker state.

        Returns:
            Current circuit breaker state
        """
        return self.circuit_breaker

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker."""
        self.circuit_breaker.reset()
        logger.info("Circuit breaker manually reset")

    def reset_metrics(self) -> None:
        """Reset client metrics."""
        self.metrics = RapiraRequestMetrics()
        logger.info("Client metrics reset")


class RapiraClientFactory:
    """Factory for creating Rapira API clients."""

    @staticmethod
    def create_client(
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
    ) -> RapiraApiClient:
        """Create a Rapira API client with configuration.

        Args:
            base_url: Base API URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay
            backoff_factor: Exponential backoff factor
            circuit_breaker_threshold: Circuit breaker failure threshold
            circuit_breaker_timeout: Circuit breaker timeout in seconds

        Returns:
            Configured Rapira API client
        """
        config = RapiraClientConfig(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            backoff_factor=backoff_factor,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_timeout=circuit_breaker_timeout,
        )

        return RapiraApiClient(config)

    @staticmethod
    def create_from_settings(settings: Any) -> RapiraApiClient:
        """Create client from application settings.

        Args:
            settings: Application settings object

        Returns:
            Configured Rapira API client
        """
        return RapiraClientFactory.create_client(
            base_url=settings.rapira_api.base_url,
            timeout=settings.rapira_api.timeout,
            max_retries=settings.rapira_api.max_retries,
            retry_delay=settings.rapira_api.retry_delay,
            backoff_factor=settings.rapira_api.backoff_factor,
            circuit_breaker_threshold=getattr(
                settings.rapira_api, "circuit_breaker_threshold", 5
            ),
            circuit_breaker_timeout=getattr(
                settings.rapira_api, "circuit_breaker_timeout", 60
            ),
        )
