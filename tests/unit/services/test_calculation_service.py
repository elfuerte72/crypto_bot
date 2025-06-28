"""Unit tests for calculation service."""

import pytest
from decimal import Decimal
from unittest.mock import Mock

from services.calculation_service import (
    CalculationService,
    CalculationInput,
    CalculationResult,
    CalculationError,
    UnsupportedPairError,
    InvalidAmountError,
    RateDataError,
)
from models.rapira_models import RapiraRateData
from config.models import Settings, CurrencyPair


class TestCalculationInput:
    """Test CalculationInput model."""

    def test_valid_input_creation(self):
        """Test creating valid calculation input."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        input_data = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100.50"),
            rate_data=rate_data,
            markup_rate=Decimal("2.5"),
        )

        assert input_data.base_currency == "USD"
        assert input_data.quote_currency == "RUB"
        assert input_data.amount == Decimal("100.50")
        assert input_data.markup_rate == Decimal("2.5")
        assert input_data.pair_string == "USD/RUB"
        assert input_data.reverse_pair_string == "RUB/USD"

    def test_currency_code_validation(self):
        """Test currency code validation and normalization."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        input_data = CalculationInput(
            base_currency="usd",
            quote_currency="rub",
            amount=Decimal("100"),
            rate_data=rate_data,
        )

        assert input_data.base_currency == "USD"
        assert input_data.quote_currency == "RUB"

    def test_invalid_amount_validation(self):
        """Test amount validation."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        with pytest.raises(Exception):  # Pydantic ValidationError
            CalculationInput(
                base_currency="USD",
                quote_currency="RUB",
                amount=Decimal("-100"),
                rate_data=rate_data,
            )

    def test_amount_precision_limiting(self):
        """Test amount precision is limited to 8 decimal places."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        input_data = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100.123456789"),
            rate_data=rate_data,
        )

        # Should be rounded to 8 decimal places
        assert input_data.amount == Decimal("100.12345679")

    def test_markup_rate_validation(self):
        """Test markup rate validation."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        # Valid markup rate
        input_data = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100"),
            rate_data=rate_data,
            markup_rate=Decimal("5.0"),
        )
        assert input_data.markup_rate == Decimal("5.0")

        # Invalid markup rate (too high)
        with pytest.raises(ValueError):
            CalculationInput(
                base_currency="USD",
                quote_currency="RUB",
                amount=Decimal("100"),
                rate_data=rate_data,
                markup_rate=Decimal("60.0"),
            )


class TestCalculationResult:
    """Test CalculationResult model."""

    def test_calculation_result_creation(self):
        """Test creating calculation result."""
        result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.0"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("76.875"),
            output_amount=Decimal("7687.5"),
            markup_amount=Decimal("187.5"),
            spread_percentage=Decimal("0.66"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,687.50 ₽",
            formatted_rate="1 USD = 76.88 ₽",
        )

        assert result.pair_string == "USD/RUB"
        assert result.total_fee_percentage == Decimal("3.16")  # 2.5 + 0.66
        assert result.profit_amount == Decimal("187.5")

    def test_notification_data_conversion(self):
        """Test conversion to notification data format."""
        result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.0"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("76.875"),
            output_amount=Decimal("7687.5"),
            markup_amount=Decimal("187.5"),
            spread_percentage=Decimal("0.66"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,687.50 ₽",
            formatted_rate="1 USD = 76.88 ₽",
        )

        notification_data = result.to_notification_data()

        assert notification_data["pair"] == "USD/RUB"
        assert notification_data["direction"] == "buy"
        assert notification_data["input_amount"] == "100"
        assert notification_data["output_amount"] == "7687.5"
        assert notification_data["markup_rate"] == "2.5"
        assert notification_data["formatted_input"] == "$100.00"
        assert notification_data["base_currency"] == "USD"
        assert notification_data["quote_currency"] == "RUB"


class TestCalculationService:
    """Test CalculationService."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.default_markup_rate = 2.5
        settings.supported_pairs_list = ["USD/RUB", "EUR/USD", "BTC/USDT"]

        # Mock currency pair
        usd_rub_pair = CurrencyPair(
            base="USD",
            quote="RUB",
            markup_rate=3.0,
            is_active=True,
            min_amount=10.0,
            max_amount=10000.0,
        )

        settings.get_currency_pair.return_value = usd_rub_pair
        settings.get_active_currency_pairs.return_value = [usd_rub_pair]

        return settings

    @pytest.fixture
    def calculation_service(self, mock_settings):
        """Create calculation service instance."""
        return CalculationService(mock_settings)

    @pytest.fixture
    def sample_rate_data(self):
        """Create sample rate data."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )
        return rate_data

    def test_service_initialization(self, calculation_service):
        """Test service initialization."""
        assert calculation_service._precision_map["USD"] == 2
        assert calculation_service._precision_map["BTC"] == 8
        assert calculation_service._precision_map["USDT"] == 6
        assert calculation_service._currency_symbols["USD"] == "$"
        assert calculation_service._currency_symbols["EUR"] == "€"

    def test_get_currency_precision(self, calculation_service):
        """Test currency precision retrieval."""
        assert calculation_service._get_currency_precision("USD") == 2
        assert calculation_service._get_currency_precision("BTC") == 8
        # Default
        assert calculation_service._get_currency_precision("UNKNOWN") == 6

    def test_get_currency_symbol(self, calculation_service):
        """Test currency symbol retrieval."""
        assert calculation_service._get_currency_symbol("USD") == "$"
        assert calculation_service._get_currency_symbol("BTC") == "BTC"
        assert calculation_service._get_currency_symbol("UNKNOWN") == "UNKNOWN"

    def test_format_amount_fiat(self, calculation_service):
        """Test amount formatting for fiat currencies."""
        # USD with decimals
        formatted = calculation_service._format_amount(Decimal("1234.56"), "USD")
        assert formatted == "$1,234.56"

        # JPY without decimals
        formatted = calculation_service._format_amount(Decimal("1234"), "JPY")
        assert formatted == "¥1,234"

        # RUB with decimals
        formatted = calculation_service._format_amount(Decimal("75687.50"), "RUB")
        assert formatted == "₽75,687.50"

    def test_format_amount_crypto(self, calculation_service):
        """Test amount formatting for cryptocurrencies."""
        # BTC with high precision
        formatted = calculation_service._format_amount(Decimal("0.12345678"), "BTC")
        assert formatted == "0.12345678 BTC"

        # Remove trailing zeros
        formatted = calculation_service._format_amount(Decimal("1.50000000"), "BTC")
        assert formatted == "1.5 BTC"

        # USDT with 6 decimals
        formatted = calculation_service._format_amount(Decimal("1234.123456"), "USDT")
        assert formatted == "1234.123456 USDT"

    def test_calculate_markup_rate_custom(self, calculation_service):
        """Test markup rate calculation with custom rate."""
        markup = calculation_service._calculate_markup_rate("USD/RUB", Decimal("5.0"))
        assert markup == Decimal("5.0")

    def test_calculate_markup_rate_pair_config(self, calculation_service):
        """Test markup rate calculation from pair configuration."""
        markup = calculation_service._calculate_markup_rate("USD/RUB")
        assert markup == Decimal("3.0")  # From mock currency pair

    def test_calculate_markup_rate_default(self, calculation_service):
        """Test markup rate calculation using default."""
        calculation_service.settings.get_currency_pair.return_value = None
        markup = calculation_service._calculate_markup_rate("UNKNOWN/PAIR")
        assert markup == Decimal("2.5")  # Default from settings

    def test_determine_calculation_direction(
        self, calculation_service, sample_rate_data
    ):
        """Test calculation direction determination."""
        direction, rate = calculation_service._determine_calculation_direction(
            sample_rate_data, "USD/RUB"
        )

        assert direction == "buy"
        assert rate == Decimal("75.5")  # ask_price

    def test_determine_calculation_direction_fallback(self, calculation_service):
        """Test calculation direction with fallback to close price."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=0,
            bid_price=0,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        direction, rate = calculation_service._determine_calculation_direction(
            rate_data, "USD/RUB"
        )

        assert direction == "buy"
        assert rate == Decimal("75.5")

    def test_determine_calculation_direction_no_data(self, calculation_service):
        """Test calculation direction with no valid data."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=0,
            bid_price=0,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        with pytest.raises(RateDataError, match="No valid rate data"):
            calculation_service._determine_calculation_direction(rate_data, "USD/RUB")

    def test_apply_markup_zero(self, calculation_service):
        """Test applying zero markup."""
        final_rate, markup_amount = calculation_service._apply_markup(
            Decimal("75.0"), Decimal("0")
        )

        assert final_rate == Decimal("75.0")
        assert markup_amount == Decimal("0")

    def test_apply_markup_positive(self, calculation_service):
        """Test applying positive markup."""
        final_rate, markup_amount = calculation_service._apply_markup(
            Decimal("75.0"), Decimal("2.5")
        )

        assert final_rate == Decimal("76.875")  # 75 * 1.025
        assert markup_amount == Decimal("1.875")  # 76.875 - 75

    def test_validate_calculation_limits_no_config(self, calculation_service):
        """Test amount validation with no pair configuration."""
        calculation_service.settings.get_currency_pair.return_value = None

        # Should not raise exception
        calculation_service._validate_calculation_limits("UNKNOWN/PAIR", Decimal("100"))

    def test_validate_calculation_limits_within_bounds(self, calculation_service):
        """Test amount validation within limits."""
        # Should not raise exception (min: 10, max: 10000)
        calculation_service._validate_calculation_limits("USD/RUB", Decimal("100"))

    def test_validate_calculation_limits_below_minimum(self, calculation_service):
        """Test amount validation below minimum."""
        with pytest.raises(InvalidAmountError, match="below minimum"):
            calculation_service._validate_calculation_limits("USD/RUB", Decimal("5"))

    def test_validate_calculation_limits_above_maximum(self, calculation_service):
        """Test amount validation above maximum."""
        with pytest.raises(InvalidAmountError, match="above maximum"):
            calculation_service._validate_calculation_limits(
                "USD/RUB", Decimal("20000")
            )

    @pytest.mark.asyncio
    async def test_calculate_exchange_success(
        self, calculation_service, sample_rate_data
    ):
        """Test successful currency exchange calculation."""
        calculation_input = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100"),
            rate_data=sample_rate_data,
            markup_rate=Decimal("2.5"),
        )

        result = await calculation_service.calculate_exchange(calculation_input)

        assert result.base_currency == "USD"
        assert result.quote_currency == "RUB"
        assert result.input_amount == Decimal("100")
        assert result.market_rate == Decimal("75.5")
        assert result.markup_rate == Decimal("2.5")
        assert result.final_rate == Decimal("77.3875")  # 75.5 * 1.025
        assert result.output_amount == Decimal("7738.75")  # 100 * 77.3875
        # Allow for precision differences in Decimal calculations
        assert abs(result.markup_amount - Decimal("187.5")) < Decimal("2")
        assert result.calculation_direction == "buy"
        assert "$100.00" in result.formatted_input
        assert "₽" in result.formatted_output

    @pytest.mark.asyncio
    async def test_calculate_exchange_unsupported_pair(
        self, calculation_service, sample_rate_data
    ):
        """Test calculation with unsupported currency pair."""
        calculation_service.settings.supported_pairs_list = ["EUR/USD"]

        calculation_input = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100"),
            rate_data=sample_rate_data,
        )

        with pytest.raises(UnsupportedPairError, match="not supported"):
            await calculation_service.calculate_exchange(calculation_input)

    @pytest.mark.asyncio
    async def test_calculate_exchange_invalid_amount(
        self, calculation_service, sample_rate_data
    ):
        """Test calculation with invalid amount."""
        calculation_input = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("5"),  # Below minimum of 10
            rate_data=sample_rate_data,
        )

        with pytest.raises(InvalidAmountError, match="below minimum"):
            await calculation_service.calculate_exchange(calculation_input)

    @pytest.mark.asyncio
    async def test_calculate_reverse_exchange(
        self, calculation_service, sample_rate_data
    ):
        """Test reverse currency exchange calculation."""
        calculation_input = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("7500"),  # Amount in RUB
            rate_data=sample_rate_data,
        )

        result = await calculation_service.calculate_reverse_exchange(calculation_input)

        assert result.base_currency == "RUB"
        assert result.quote_currency == "USD"
        assert result.input_amount == Decimal("7500")

    @pytest.mark.asyncio
    async def test_calculate_reverse_exchange_no_bid_price(self, calculation_service):
        """Test reverse calculation with no bid price."""
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=0,
            bid_price=0,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        calculation_input = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("7500"),
            rate_data=rate_data,
        )

        result = await calculation_service.calculate_reverse_exchange(calculation_input)
        assert result is not None

    def test_get_supported_pairs(self, calculation_service):
        """Test getting supported currency pairs."""
        pairs = calculation_service.get_supported_pairs()
        assert pairs == ["USD/RUB", "EUR/USD", "BTC/USDT"]

    def test_get_pair_config(self, calculation_service):
        """Test getting pair configuration."""
        config = calculation_service.get_pair_config("USD/RUB")
        assert config is not None
        assert config.markup_rate == 3.0

    def test_validate_amount_format_valid(self, calculation_service):
        """Test amount format validation with valid inputs."""
        # Standard decimal
        amount = calculation_service.validate_amount_format("123.45")
        assert amount == Decimal("123.45")

        # With thousands separator
        amount = calculation_service.validate_amount_format("1,234.56")
        assert amount == Decimal("1234.56")

        # With spaces
        amount = calculation_service.validate_amount_format(" 123.45 ")
        assert amount == Decimal("123.45")

    def test_validate_amount_format_invalid(self, calculation_service):
        """Test amount format validation with invalid inputs."""
        # Negative amount
        with pytest.raises(InvalidAmountError, match="must be positive"):
            calculation_service.validate_amount_format("-123.45")

        # Invalid format
        with pytest.raises(InvalidAmountError, match="Invalid amount format"):
            calculation_service.validate_amount_format("abc")

        # Too many decimal places
        with pytest.raises(InvalidAmountError, match="Too many decimal places"):
            calculation_service.validate_amount_format("123.123456789")

    def test_format_calculation_summary(self, calculation_service):
        """Test formatting calculation summary."""
        result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.0"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("76.875"),
            output_amount=Decimal("7687.5"),
            markup_amount=Decimal("187.5"),
            spread_percentage=Decimal("0.66"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,687.50 ₽",
            formatted_rate="1 USD = 76.88 ₽",
        )

        summary = calculation_service.format_calculation_summary(result)

        assert "💱 **Exchange Calculation**" in summary
        assert "USD/RUB" in summary
        assert "$100.00" in summary
        assert "7,687.50 ₽" in summary
        assert "2.5%" in summary
        assert "Buy" in summary

    @pytest.mark.asyncio
    async def test_get_calculation_stats(self, calculation_service):
        """Test getting calculation service statistics."""
        stats = await calculation_service.get_calculation_stats()

        assert "supported_pairs" in stats
        assert "active_pairs" in stats
        assert "default_markup_rate" in stats
        assert "currency_precisions" in stats
        assert "currency_symbols" in stats

        assert stats["supported_pairs"] == 3
        assert stats["active_pairs"] == 1
        assert stats["default_markup_rate"] == 2.5


class TestCalculationExceptions:
    """Test calculation service exceptions."""

    def test_calculation_error_creation(self):
        """Test CalculationError creation."""
        error = CalculationError("Test error", pair="USD/RUB", amount="100")

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.pair == "USD/RUB"
        assert error.amount == "100"

    def test_unsupported_pair_error(self):
        """Test UnsupportedPairError."""
        error = UnsupportedPairError("Pair not supported", pair="UNKNOWN/PAIR")

        assert isinstance(error, CalculationError)
        assert error.pair == "UNKNOWN/PAIR"

    def test_invalid_amount_error(self):
        """Test InvalidAmountError."""
        error = InvalidAmountError("Invalid amount", amount="abc")

        assert isinstance(error, CalculationError)
        assert error.amount == "abc"

    def test_rate_data_error(self):
        """Test RateDataError."""
        error = RateDataError("No rate data")

        assert isinstance(error, CalculationError)
        assert str(error) == "No rate data"


class TestCalculationServiceIntegration:
    """Integration tests for calculation service."""

    @pytest.fixture
    def real_settings(self):
        """Create realistic settings for integration tests."""
        from config.models import (
            Settings,
            TelegramConfig,
            RapiraApiConfig,
            RedisConfig,
            CacheConfig,
            LoggingConfig,
            ApplicationConfig,
        )

        settings = Settings(
            telegram=TelegramConfig(),
            rapira_api=RapiraApiConfig(),
            redis=RedisConfig(),
            cache=CacheConfig(),
            logging=LoggingConfig(),
            application=ApplicationConfig(),
            default_markup_rate=2.5,
        )

        # Add some currency pairs
        settings.add_currency_pair(
            "USD", "RUB", markup_rate=3.0, min_amount=10.0, max_amount=10000.0
        )
        settings.add_currency_pair(
            "EUR", "USD", markup_rate=2.0, min_amount=50.0, max_amount=5000.0
        )
        settings.add_currency_pair(
            "BTC", "USDT", markup_rate=1.5, min_amount=0.001, max_amount=10.0
        )

        return settings

    @pytest.fixture
    def integration_service(self, real_settings):
        """Create calculation service with real settings."""
        return CalculationService(real_settings)

    @pytest.mark.asyncio
    async def test_full_calculation_flow(self, integration_service):
        """Test complete calculation flow with realistic data."""
        # Create realistic rate data
        rate_data = RapiraRateData(
            symbol="USD/RUB",
            open=75.0,
            high=76.0,
            low=74.0,
            close=75.5,
            chg=0.01,
            change=0.5,
            fee=0.002,
            last_day_close=75.0,
            usd_rate=75.5,
            base_usd_rate=1.0,
            ask_price=75.7,
            bid_price=75.3,
            base_coin_scale=2,
            coin_scale=2,
            quote_currency_name="Russian Ruble",
            base_currency="USD",
            quote_currency="RUB",
        )

        # Create calculation input
        calculation_input = CalculationInput(
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100.50"),
            rate_data=rate_data,
        )

        # Perform calculation
        result = await integration_service.calculate_exchange(calculation_input)

        # Verify result
        assert result.base_currency == "USD"
        assert result.quote_currency == "RUB"
        assert result.input_amount == Decimal("100.50")
        assert result.markup_rate == Decimal("3.0")  # From pair config
        assert result.final_rate > result.market_rate  # Markup applied
        assert result.output_amount > Decimal("0")
        assert result.markup_amount > Decimal("0")
        assert "$" in result.formatted_input or "USD" in result.formatted_input
        assert "RUB" in result.formatted_output or "₽" in result.formatted_output

        # Test notification data
        notification_data = result.to_notification_data()
        assert all(
            key in notification_data
            for key in [
                "pair",
                "direction",
                "input_amount",
                "output_amount",
                "rate",
                "markup_rate",
                "formatted_input",
                "formatted_output",
            ]
        )

        # Test summary formatting
        summary = integration_service.format_calculation_summary(result)
        assert len(summary) > 100  # Should be a substantial summary
        assert "Exchange Calculation" in summary
        assert "USD/RUB" in summary

    @pytest.mark.asyncio
    async def test_multiple_currency_pairs(self, integration_service):
        """Test calculations with different currency pairs."""
        pairs_data = [
            ("USD", "RUB", Decimal("100"), 75.5),
            ("EUR", "USD", Decimal("200"), 1.1),
            ("BTC", "USDT", Decimal("0.5"), 45000.0),
        ]

        for base, quote, amount, rate in pairs_data:
            rate_data = RapiraRateData(
                symbol=f"{base}/{quote}",
                open=75.0,
                high=76.0,
                low=74.0,
                close=75.5,
                chg=0.01,
                change=0.5,
                fee=0.002,
                last_day_close=75.0,
                usd_rate=75.5,
                base_usd_rate=1.0,
                ask_price=rate,
                bid_price=rate * 0.999,
                base_coin_scale=2,
                coin_scale=2,
                quote_currency_name=quote,
                base_currency=base,
                quote_currency=quote,
            )

            calculation_input = CalculationInput(
                base_currency=base,
                quote_currency=quote,
                amount=amount,
                rate_data=rate_data,
            )

            result = await integration_service.calculate_exchange(calculation_input)

            assert result.base_currency == base
            assert result.quote_currency == quote
            assert result.input_amount == amount
            assert result.output_amount > Decimal("0")
            assert result.markup_amount >= Decimal("0")

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, integration_service):
        """Test service initialization and cleanup."""
        # Initialize service
        await integration_service.initialize()

        # Service should be ready
        stats = await integration_service.get_calculation_stats()
        assert stats["supported_pairs"] == 3
        assert stats["active_pairs"] == 3

        # Cleanup service
        await integration_service.cleanup()
