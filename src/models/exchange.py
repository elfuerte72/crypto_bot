"""Exchange-related data models."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CurrencyPair(BaseModel):
    """Currency pair model."""
    
    base_currency: str = Field(..., description="Base currency code")
    quote_currency: str = Field(..., description="Quote currency code")
    
    @property
    def symbol(self) -> str:
        """Get currency pair symbol."""
        return f"{self.base_currency}/{self.quote_currency}"
    
    @property
    def reverse_symbol(self) -> str:
        """Get reverse currency pair symbol."""
        return f"{self.quote_currency}/{self.base_currency}"
    
    @classmethod
    def from_symbol(cls, symbol: str) -> "CurrencyPair":
        """Create currency pair from symbol string."""
        if "/" not in symbol:
            raise ValueError(f"Invalid currency pair symbol: {symbol}")
        
        base, quote = symbol.split("/", 1)
        return cls(base_currency=base.strip(), quote_currency=quote.strip())


class ExchangeRate(BaseModel):
    """Exchange rate model."""
    
    currency_pair: CurrencyPair
    rate: Decimal = Field(..., description="Exchange rate")
    markup_rate: Optional[Decimal] = Field(None, description="Markup percentage")
    final_rate: Optional[Decimal] = Field(None, description="Final rate with markup")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="rapira", description="Rate source")
    
    def apply_markup(self, markup_percentage: Decimal) -> "ExchangeRate":
        """Apply markup to the exchange rate."""
        markup_multiplier = 1 + (markup_percentage / 100)
        final_rate = self.rate * markup_multiplier
        
        return self.copy(
            markup_rate=markup_percentage,
            final_rate=final_rate
        )


class CalculationRequest(BaseModel):
    """Calculation request model."""
    
    currency_pair: CurrencyPair
    amount: Decimal = Field(..., description="Amount to convert")
    user_id: int = Field(..., description="User ID making the request")
    markup_rate: Optional[Decimal] = Field(None, description="Custom markup rate")


class CalculationResult(BaseModel):
    """Calculation result model."""
    
    request: CalculationRequest
    exchange_rate: ExchangeRate
    converted_amount: Decimal = Field(..., description="Converted amount")
    markup_amount: Optional[Decimal] = Field(None, description="Markup amount")
    total_amount: Decimal = Field(..., description="Total amount with markup")
    calculation_id: str = Field(..., description="Unique calculation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)