"""Rapira API data models.

This module contains Pydantic models for Rapira API requests and responses,
providing type safety and validation for all API interactions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RapiraRateData(BaseModel):
    """Individual rate data from Rapira API."""

    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC/USDT')")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price in 24h")
    low: float = Field(..., description="Lowest price in 24h")
    close: float = Field(..., description="Current/closing price")
    chg: float = Field(..., description="Change as decimal (e.g., 0.01 = 1%)")
    change: float = Field(..., description="Absolute change amount")
    fee: float = Field(..., description="Trading fee rate")
    last_day_close: float = Field(
        ..., alias="lastDayClose", description="Previous day closing price"
    )
    usd_rate: float = Field(..., alias="usdRate", description="Rate in USD")
    base_usd_rate: float = Field(
        ..., alias="baseUsdRate", description="Base currency USD rate"
    )
    ask_price: float = Field(..., alias="askPrice", description="Ask (sell) price")
    bid_price: float = Field(..., alias="bidPrice", description="Bid (buy) price")
    base_coin_scale: int = Field(
        ..., alias="baseCoinScale", description="Base currency decimal places"
    )
    coin_scale: int = Field(
        ..., alias="coinScale", description="Quote currency decimal places"
    )
    quote_currency_name: str = Field(
        ..., alias="quoteCurrencyName", description="Quote currency full name"
    )
    base_currency: str = Field(
        ..., alias="baseCurrency", description="Base currency code"
    )
    quote_currency: str = Field(
        ..., alias="quoteCurrency", description="Quote currency code"
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        if "/" not in v:
            raise ValueError(
                f"Invalid symbol format: {v}. Expected format: 'BASE/QUOTE'"
            )
        return v

    @property
    def base_quote_pair(self) -> tuple[str, str]:
        """Get base and quote currencies as tuple."""
        parts = self.symbol.split("/")
        return parts[0], parts[1]

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask_price - self.bid_price

    @property
    def spread_percentage(self) -> float:
        """Calculate bid-ask spread as percentage."""
        if self.ask_price == 0:
            return 0.0
        return (self.spread / self.ask_price) * 100

    @property
    def change_percentage(self) -> float:
        """Get change as percentage (0-100 scale)."""
        return self.chg * 100

    @property
    def is_positive_change(self) -> bool:
        """Check if price change is positive."""
        return self.change > 0


class RapiraApiResponse(BaseModel):
    """Rapira API response wrapper."""

    data: list[RapiraRateData] = Field(..., description="List of rate data")
    code: int = Field(..., description="Response code (0 = success)")
    message: str = Field(..., description="Response message")
    total_page: int | None = Field(
        None, alias="totalPage", description="Total pages (if paginated)"
    )
    total_element: int | None = Field(
        None, alias="totalElement", description="Total elements (if paginated)"
    )
    is_working: int = Field(
        ..., alias="isWorking", description="API working status (1 = working)"
    )

    @field_validator("code")
    @classmethod
    def validate_success_code(cls, v: int) -> int:
        """Validate that response code indicates success."""
        if v != 0:
            raise ValueError(f"API returned error code: {v}")
        return v

    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.code == 0

    @property
    def is_api_working(self) -> bool:
        """Check if API is working."""
        return self.is_working == 1

    def get_rate_by_symbol(self, symbol: str) -> RapiraRateData | None:
        """Get rate data by symbol."""
        for rate in self.data:
            if rate.symbol == symbol:
                return rate
        return None

    def get_supported_symbols(self) -> list[str]:
        """Get list of all supported symbols."""
        return [rate.symbol for rate in self.data]


class RapiraApiError(BaseModel):
    """Rapira API error response."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: str | None = Field(None, description="Additional error details")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Error timestamp"
    )

    @property
    def is_client_error(self) -> bool:
        """Check if error is client-side (4xx)."""
        return 400 <= self.code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if error is server-side (5xx)."""
        return 500 <= self.code < 600

    @property
    def is_rate_limit_error(self) -> bool:
        """Check if error is rate limiting (429)."""
        return self.code == 429


class RapiraClientConfig(BaseModel):
    """Configuration for Rapira API client."""

    base_url: str = Field(..., description="Base API URL")
    timeout: int = Field(
        default=30, ge=5, le=120, description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum retry attempts"
    )
    retry_delay: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Initial retry delay"
    )
    backoff_factor: float = Field(
        default=2.0, ge=1.0, le=5.0, description="Exponential backoff factor"
    )
    circuit_breaker_threshold: int = Field(
        default=5, ge=1, le=20, description="Circuit breaker failure threshold"
    )
    circuit_breaker_timeout: int = Field(
        default=60, ge=10, le=300, description="Circuit breaker timeout in seconds"
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v.rstrip("/")


class CircuitBreakerState(BaseModel):
    """Circuit breaker state tracking."""

    failure_count: int = Field(default=0, description="Current failure count")
    last_failure_time: datetime | None = Field(
        None, description="Last failure timestamp"
    )
    state: str = Field(
        default="closed", description="Circuit state: closed, open, half-open"
    )

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == "closed"

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == "open"

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == "half_open"

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"

    def record_failure(self) -> None:
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

    def open_circuit(self) -> None:
        """Open the circuit."""
        self.state = "open"

    def half_open_circuit(self) -> None:
        """Set circuit to half-open state."""
        self.state = "half_open"


class RapiraRequestMetrics(BaseModel):
    """Metrics for Rapira API requests."""

    total_requests: int = Field(default=0, description="Total requests made")
    successful_requests: int = Field(default=0, description="Successful requests")
    failed_requests: int = Field(default=0, description="Failed requests")
    avg_response_time: float = Field(
        default=0.0, description="Average response time in seconds"
    )
    last_request_time: datetime | None = Field(
        None, description="Last request timestamp"
    )
    last_success_time: datetime | None = Field(
        None, description="Last successful request timestamp"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    def record_request(self, success: bool, response_time: float) -> None:
        """Record a request."""
        self.total_requests += 1
        self.last_request_time = datetime.now()

        if success:
            self.successful_requests += 1
            self.last_success_time = datetime.now()
        else:
            self.failed_requests += 1

        # Update average response time
        if self.total_requests == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                self.avg_response_time * (self.total_requests - 1) + response_time
            ) / self.total_requests
