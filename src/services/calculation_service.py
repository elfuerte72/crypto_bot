"""Calculation service for currency exchange calculations.

This module provides comprehensive calculation logic for applying markup rates,
handling precision, formatting results, and preparing notification data.
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from ..config.models import CurrencyPair, Settings
from ..models.rapira_models import RapiraRateData
from .base import BaseService

logger = logging.getLogger(__name__)


class CalculationInput(BaseModel):
    """Input data for calculation."""

    base_currency: str = Field(
        ..., description="Base currency code", min_length=3, max_length=5
    )
    quote_currency: str = Field(
        ..., description="Quote currency code", min_length=3, max_length=5
    )
    amount: Decimal = Field(..., gt=0, description="Amount to convert")
    rate_data: RapiraRateData = Field(
        ..., description="Market rate data from Rapira API"
    )
    markup_rate: Optional[Decimal] = Field(
        None, ge=0, le=50, description="Custom markup rate in percentage"
    )

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def validate_currency_codes(cls, v: str) -> str:
        """Validate currency code format."""
        return v.upper().strip()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount precision."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        # Limit to 8 decimal places
        return v.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    @property
    def pair_string(self) -> str:
        """Get currency pair as string."""
        return f"{self.base_currency}/{self.quote_currency}"

    @property
    def reverse_pair_string(self) -> str:
        """Get reverse currency pair as string."""
        return f"{self.quote_currency}/{self.base_currency}"


class CalculationResult(BaseModel):
    """Result of currency calculation."""

    base_currency: str = Field(..., description="Base currency code")
    quote_currency: str = Field(..., description="Quote currency code")
    input_amount: Decimal = Field(..., description="Original input amount")
    market_rate: Decimal = Field(..., description="Market exchange rate")
    markup_rate: Decimal = Field(..., description="Applied markup rate in percentage")
    final_rate: Decimal = Field(..., description="Final rate with markup applied")
    output_amount: Decimal = Field(..., description="Calculated output amount")
    markup_amount: Decimal = Field(..., description="Markup amount in quote currency")
    spread_percentage: Decimal = Field(..., description="Bid-ask spread percentage")
    calculation_direction: str = Field(
        ..., description="Calculation direction (buy/sell)"
    )
    formatted_input: str = Field(
        ..., description="Formatted input amount with currency"
    )
    formatted_output: str = Field(
        ..., description="Formatted output amount with currency"
    )
    formatted_rate: str = Field(..., description="Formatted exchange rate")

    @property
    def pair_string(self) -> str:
        """Get currency pair as string."""
        return f"{self.base_currency}/{self.quote_currency}"

    @property
    def total_fee_percentage(self) -> Decimal:
        """Get total fee percentage (markup + spread)."""
        return self.markup_rate + self.spread_percentage

    @property
    def profit_amount(self) -> Decimal:
        """Get profit amount from markup."""
        return self.markup_amount

    def to_notification_data(self) -> Dict[str, Any]:
        """Convert to notification data format."""
        return {
            "pair": self.pair_string,
            "direction": self.calculation_direction,
            "input_amount": str(self.input_amount),
            "output_amount": str(self.output_amount),
            "rate": str(self.final_rate),
            "markup_rate": str(self.markup_rate),
            "markup_amount": str(self.markup_amount),
            "formatted_input": self.formatted_input,
            "formatted_output": self.formatted_output,
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
        }


class CalculationError(Exception):
    """Base exception for calculation errors."""

    def __init__(self, message: str, pair: str = "", amount: str = ""):
        super().__init__(message)
        self.message = message
        self.pair = pair
        self.amount = amount


class UnsupportedPairError(CalculationError):
    """Currency pair not supported."""

    pass


class InvalidAmountError(CalculationError):
    """Invalid amount for calculation."""

    pass


class RateDataError(CalculationError):
    """Invalid or missing rate data."""

    pass


class CalculationService(BaseService):
    """Service for currency exchange calculations with markup logic."""

    def __init__(self, settings: Settings):
        """Initialize calculation service.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        self._precision_map: Dict[str, int] = {}
        self._currency_symbols: Dict[str, str] = {}
        self._initialize_currency_data()

    async def initialize(self) -> None:
        """Initialize calculation service."""
        logger.info("Calculation service initialized")

    async def cleanup(self) -> None:
        """Cleanup calculation service resources."""
        logger.info("Calculation service cleaned up")

    def _initialize_currency_data(self) -> None:
        """Initialize currency precision and symbol mappings."""
        # Default precision for different currency types
        self._precision_map = {
            # Fiat currencies - 2 decimal places
            "USD": 2,
            "EUR": 2,
            "GBP": 2,
            "JPY": 0,
            "CHF": 2,
            "CAD": 2,
            "AUD": 2,
            "NZD": 2,
            "SEK": 2,
            "NOK": 2,
            "DKK": 2,
            "PLN": 2,
            "CZK": 2,
            "HUF": 0,
            "RUB": 2,
            "CNY": 2,
            "KRW": 0,
            "INR": 2,
            "BRL": 2,
            "MXN": 2,
            "ZAR": 2,
            "TRY": 2,
            "SGD": 2,
            "HKD": 2,
            "THB": 2,
            # Major cryptocurrencies - 8 decimal places
            "BTC": 8,
            "ETH": 8,
            "LTC": 8,
            "BCH": 8,
            "XRP": 6,
            "ADA": 6,
            "DOT": 4,
            "LINK": 4,
            "UNI": 4,
            "AAVE": 4,
            # Stablecoins - 6 decimal places
            "USDT": 6,
            "USDC": 6,
            "BUSD": 6,
            "DAI": 6,
            "TUSD": 6,
            # Other cryptocurrencies - 6 decimal places (default)
        }

        # Currency symbols for formatting
        self._currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "CHF": "CHF",
            "CAD": "C$",
            "AUD": "A$",
            "NZD": "NZ$",
            "RUB": "₽",
            "CNY": "¥",
            "KRW": "₩",
            "INR": "₹",
            "BRL": "R$",
            "MXN": "$",
            "TRY": "₺",
            "SGD": "S$",
            "HKD": "HK$",
            "THB": "฿",
            # Cryptocurrencies use their code as symbol
            "BTC": "BTC",
            "ETH": "ETH",
            "LTC": "LTC",
            "BCH": "BCH",
            "XRP": "XRP",
            "ADA": "ADA",
            "DOT": "DOT",
            "LINK": "LINK",
            "USDT": "USDT",
            "USDC": "USDC",
            "BUSD": "BUSD",
            "DAI": "DAI",
        }

    def _get_currency_precision(self, currency: str) -> int:
        """Get decimal precision for currency.

        Args:
            currency: Currency code

        Returns:
            Number of decimal places
        """
        return self._precision_map.get(
            currency.upper(), 6
        )  # Default to 6 for unknown currencies

    def _get_currency_symbol(self, currency: str) -> str:
        """Get currency symbol for formatting.

        Args:
            currency: Currency code

        Returns:
            Currency symbol or code
        """
        return self._currency_symbols.get(currency.upper(), currency.upper())

    def _format_amount(self, amount: Decimal, currency: str) -> str:
        """Format amount with currency symbol and proper precision.

        Args:
            amount: Amount to format
            currency: Currency code

        Returns:
            Formatted amount string
        """
        precision = self._get_currency_precision(currency)
        symbol = self._get_currency_symbol(currency)

        # Quantize to proper precision
        quantized_amount = amount.quantize(
            Decimal("0.1") ** precision, rounding=ROUND_HALF_UP
        )

        # Format with thousands separators for fiat currencies
        if currency.upper() in ["USD", "EUR", "GBP", "RUB", "CNY", "JPY", "KRW"]:
            if precision == 0:
                formatted = f"{quantized_amount:,.0f}"
            else:
                formatted = f"{quantized_amount:,.{precision}f}"
        else:
            # Cryptocurrencies - no thousands separators, remove trailing zeros
            formatted = f"{quantized_amount:.{precision}f}".rstrip("0").rstrip(".")
            if "." not in formatted:
                formatted += ".0" if precision > 0 else ""

        # Add currency symbol
        if symbol in ["$", "€", "£", "¥", "₽", "₩", "₹", "R$", "₺"]:
            return f"{symbol}{formatted}"
        else:
            return f"{formatted} {symbol}"

    def _calculate_markup_rate(
        self, pair_string: str, custom_markup: Optional[Decimal] = None
    ) -> Decimal:
        """Calculate markup rate for currency pair.

        Args:
            pair_string: Currency pair string (e.g., 'USD/RUB')
            custom_markup: Custom markup rate to use instead of configured

        Returns:
            Markup rate as decimal percentage
        """
        if custom_markup is not None:
            return custom_markup

        # Try to get pair-specific markup rate
        currency_pair = self.settings.get_currency_pair(pair_string)
        if currency_pair:
            return Decimal(str(currency_pair.markup_rate))

        # Fall back to default markup rate
        return Decimal(str(self.settings.default_markup_rate))

    def _determine_calculation_direction(
        self, rate_data: RapiraRateData, pair_string: str
    ) -> Tuple[str, Decimal]:
        """Determine calculation direction and select appropriate rate.

        Args:
            rate_data: Market rate data
            pair_string: Currency pair string

        Returns:
            Tuple of (direction, rate) where direction is 'buy' or 'sell'
        """
        # For most calculations, we use the ask price (what customer pays)
        # This represents buying the base currency with quote currency
        if rate_data.ask_price > 0:
            return "buy", Decimal(str(rate_data.ask_price))

        # Fallback to close price if ask price is not available
        if rate_data.close > 0:
            return "buy", Decimal(str(rate_data.close))

        raise RateDataError(f"No valid rate data available for {pair_string}")

    def _apply_markup(
        self, base_rate: Decimal, markup_percentage: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Apply markup to base rate.

        Args:
            base_rate: Base exchange rate
            markup_percentage: Markup percentage to apply

        Returns:
            Tuple of (final_rate, markup_amount)
        """
        if markup_percentage <= 0:
            return base_rate, Decimal("0")

        # Calculate markup amount
        markup_multiplier = Decimal("1") + (markup_percentage / Decimal("100"))
        final_rate = base_rate * markup_multiplier
        markup_amount = final_rate - base_rate

        return final_rate, markup_amount

    def _validate_calculation_limits(self, pair_string: str, amount: Decimal) -> None:
        """Validate calculation amount against pair limits.

        Args:
            pair_string: Currency pair string
            amount: Amount to validate

        Raises:
            InvalidAmountError: If amount is outside limits
        """
        currency_pair = self.settings.get_currency_pair(pair_string)
        if not currency_pair:
            return  # No limits configured

        if currency_pair.min_amount is not None and amount < Decimal(
            str(currency_pair.min_amount)
        ):
            raise InvalidAmountError(
                f"Amount {amount} is below minimum {currency_pair.min_amount} for {pair_string}",
                pair=pair_string,
                amount=str(amount),
            )

        if currency_pair.max_amount is not None and amount > Decimal(
            str(currency_pair.max_amount)
        ):
            raise InvalidAmountError(
                f"Amount {amount} is above maximum {currency_pair.max_amount} for {pair_string}",
                pair=pair_string,
                amount=str(amount),
            )

    async def calculate_exchange(
        self, calculation_input: CalculationInput
    ) -> CalculationResult:
        """Calculate currency exchange with markup.

        Args:
            calculation_input: Calculation input data

        Returns:
            Calculation result with all details

        Raises:
            CalculationError: For various calculation errors
        """
        try:
            # Validate pair is supported
            pair_string = calculation_input.pair_string
            if pair_string not in self.settings.supported_pairs_list:
                # Try reverse pair
                reverse_pair = calculation_input.reverse_pair_string
                if reverse_pair not in self.settings.supported_pairs_list:
                    raise UnsupportedPairError(
                        f"Currency pair {pair_string} is not supported"
                    )
                # Use reverse pair logic would go here, but for now we'll keep it simple

            # Validate amount limits
            self._validate_calculation_limits(pair_string, calculation_input.amount)

            # Get market rate and direction
            direction, market_rate = self._determine_calculation_direction(
                calculation_input.rate_data, pair_string
            )

            # Calculate markup rate
            markup_rate = self._calculate_markup_rate(
                pair_string, calculation_input.markup_rate
            )

            # Apply markup to get final rate
            final_rate, markup_amount_per_unit = self._apply_markup(
                market_rate, markup_rate
            )

            # Calculate output amount
            output_amount = calculation_input.amount * final_rate

            # Calculate total markup amount
            total_markup_amount = calculation_input.amount * markup_amount_per_unit

            # Calculate spread percentage
            spread_percentage = Decimal(
                str(calculation_input.rate_data.spread_percentage)
            )

            # Format amounts
            formatted_input = self._format_amount(
                calculation_input.amount, calculation_input.base_currency
            )
            formatted_output = self._format_amount(
                output_amount, calculation_input.quote_currency
            )
            formatted_rate = f"1 {calculation_input.base_currency} = {self._format_amount(final_rate, calculation_input.quote_currency)}"

            # Create result
            result = CalculationResult(
                base_currency=calculation_input.base_currency,
                quote_currency=calculation_input.quote_currency,
                input_amount=calculation_input.amount,
                market_rate=market_rate,
                markup_rate=markup_rate,
                final_rate=final_rate,
                output_amount=output_amount,
                markup_amount=total_markup_amount,
                spread_percentage=spread_percentage,
                calculation_direction=direction,
                formatted_input=formatted_input,
                formatted_output=formatted_output,
                formatted_rate=formatted_rate,
            )

            logger.debug(
                f"Calculation completed: {formatted_input} -> {formatted_output} "
                f"(rate: {formatted_rate}, markup: {markup_rate}%)"
            )

            return result

        except (UnsupportedPairError, InvalidAmountError, RateDataError):
            raise
        except Exception as e:
            logger.error(f"Calculation error for {calculation_input.pair_string}: {e}")
            raise CalculationError(
                f"Calculation failed: {e}", pair=calculation_input.pair_string
            )

    async def calculate_reverse_exchange(
        self, calculation_input: CalculationInput
    ) -> CalculationResult:
        """Calculate reverse currency exchange (quote -> base).

        Args:
            calculation_input: Calculation input data (amount in quote currency)

        Returns:
            Calculation result for reverse exchange

        Raises:
            CalculationError: For various calculation errors
        """
        try:
            # For reverse calculation, we need to use bid price (what we pay to buy quote currency)
            rate_data = calculation_input.rate_data

            if rate_data.bid_price <= 0:
                if rate_data.close <= 0:
                    raise RateDataError(
                        f"No valid reverse rate data for {calculation_input.pair_string}"
                    )
                reverse_rate = Decimal("1") / Decimal(str(rate_data.close))
            else:
                reverse_rate = Decimal("1") / Decimal(str(rate_data.bid_price))

            # Create reverse calculation input
            reverse_input = CalculationInput(
                base_currency=calculation_input.quote_currency,
                quote_currency=calculation_input.base_currency,
                amount=calculation_input.amount,
                rate_data=calculation_input.rate_data,
                markup_rate=calculation_input.markup_rate,
            )

            # Use the reverse rate as market rate
            reverse_input.rate_data.ask_price = float(reverse_rate)

            # Calculate using normal flow
            result = await self.calculate_exchange(reverse_input)

            logger.debug(
                f"Reverse calculation completed for {calculation_input.pair_string}"
            )
            return result

        except Exception as e:
            logger.error(
                f"Reverse calculation error for {calculation_input.pair_string}: {e}"
            )
            raise CalculationError(
                f"Reverse calculation failed: {e}", pair=calculation_input.pair_string
            )

    def get_supported_pairs(self) -> list[str]:
        """Get list of supported currency pairs.

        Returns:
            List of supported pair strings
        """
        return self.settings.supported_pairs_list

    def get_pair_config(self, pair_string: str) -> Optional[CurrencyPair]:
        """Get currency pair configuration.

        Args:
            pair_string: Currency pair string

        Returns:
            Currency pair configuration or None
        """
        return self.settings.get_currency_pair(pair_string)

    def validate_amount_format(self, amount_str: str) -> Decimal:
        """Validate and parse amount string.

        Args:
            amount_str: Amount as string

        Returns:
            Parsed amount as Decimal

        Raises:
            InvalidAmountError: If amount format is invalid
        """
        try:
            # Remove common separators and whitespace
            cleaned = amount_str.replace(",", "").replace(" ", "").strip()

            # Parse as Decimal for precision
            amount = Decimal(cleaned)

            if amount <= 0:
                raise InvalidAmountError("Amount must be positive", amount=amount_str)

            # Limit precision to prevent overflow
            if amount.as_tuple().exponent < -8:
                raise InvalidAmountError(
                    "Too many decimal places (max 8)", amount=amount_str
                )

            return amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

        except (ValueError, TypeError, ArithmeticError) as e:
            raise InvalidAmountError(f"Invalid amount format: {e}", amount=amount_str)

    def format_calculation_summary(self, result: CalculationResult) -> str:
        """Format calculation result as summary text.

        Args:
            result: Calculation result

        Returns:
            Formatted summary string
        """
        lines = [
            f"💱 **Exchange Calculation**",
            f"",
            f"📊 **Rate Information:**",
            f"• Pair: {result.pair_string}",
            f"• Market Rate: {result.formatted_rate}",
            f"• Markup: {result.markup_rate}% (+{self._format_amount(result.markup_amount, result.quote_currency)})",
            f"• Spread: {result.spread_percentage:.2f}%",
            f"",
            f"💰 **Calculation:**",
            f"• You send: {result.formatted_input}",
            f"• You receive: {result.formatted_output}",
            f"• Direction: {result.calculation_direction.title()}",
            f"",
            f"📈 **Fees & Profit:**",
            f"• Our profit: {self._format_amount(result.markup_amount, result.quote_currency)}",
            f"• Total fee: {result.total_fee_percentage:.2f}%",
        ]

        return "\n".join(lines)

    async def get_calculation_stats(self) -> Dict[str, Any]:
        """Get calculation service statistics.

        Returns:
            Dictionary with service statistics
        """
        return {
            "supported_pairs": len(self.settings.supported_pairs_list),
            "active_pairs": len(self.settings.get_active_currency_pairs()),
            "default_markup_rate": float(self.settings.default_markup_rate),
            "currency_precisions": len(self._precision_map),
            "currency_symbols": len(self._currency_symbols),
        }
