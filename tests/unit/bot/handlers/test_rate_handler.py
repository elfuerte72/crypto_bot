"""Unit tests for rate command handler.

This module contains comprehensive tests for the /rate command handler,
including rate service functionality, error handling, and user interactions.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery, Message

from src.bot.handlers.rate_handler import (
    RateService,
    cmd_rate,
    get_rate_service,
    handle_back_to_rate_selection,
    handle_currency_selection,
)
from src.config.models import Settings
from src.models.rapira_models import RapiraRateData
from src.services.rapira_client import RapiraApiException


class TestRateService:
    """Test cases for RateService class."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        settings = Settings()
        # Add test currency pairs
        settings.add_currency_pair("RUB", "USD", markup_rate=2.5)
        settings.add_currency_pair("USDT", "RUB", markup_rate=3.0)
        return settings

    @pytest.fixture
    def rate_service(self, settings: Settings) -> RateService:
        """Create test rate service."""
        return RateService(settings)

    @pytest.fixture
    def sample_rate_data(self) -> RapiraRateData:
        """Create sample rate data."""
        return RapiraRateData(
            symbol="RUB/USD",
            open=0.0105,
            high=0.0107,
            low=0.0104,
            close=0.0106,
            chg=0.0095,
            change=0.0001,
            fee=0.001,
            lastDayClose=0.0105,
            usdRate=0.0106,
            baseUsdRate=0.0106,
            askPrice=0.0107,
            bidPrice=0.0105,
            baseCoinScale=2,
            coinScale=4,
            quoteCurrencyName="US Dollar",
            baseCurrency="RUB",
            quoteCurrency="USD",
        )

    async def test_init(self, settings: Settings) -> None:
        """Test RateService initialization."""
        service = RateService(settings)
        assert service.settings == settings
        assert service._api_client is None

    async def test_get_api_client_creates_client(
        self, rate_service: RateService
    ) -> None:
        """Test that get_api_client creates client on first call."""
        with patch(
            "src.bot.handlers.rate_handler.RapiraClientFactory.create_from_settings"
        ) as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client

            client = await rate_service.get_api_client()

            assert client == mock_client
            assert rate_service._api_client == mock_client
            mock_factory.assert_called_once_with(rate_service.settings)

    async def test_get_api_client_reuses_client(
        self, rate_service: RateService
    ) -> None:
        """Test that get_api_client reuses existing client."""
        with patch(
            "src.bot.handlers.rate_handler.RapiraClientFactory.create_from_settings"
        ) as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client

            # First call
            client1 = await rate_service.get_api_client()
            # Second call
            client2 = await rate_service.get_api_client()

            assert client1 == client2
            assert mock_factory.call_count == 1

    async def test_get_rate_for_pair_success(
        self, rate_service: RateService, sample_rate_data: RapiraRateData
    ) -> None:
        """Test successful rate retrieval."""
        with patch.object(rate_service, "get_api_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_rate_by_symbol.return_value = sample_rate_data
            mock_get_client.return_value = mock_client

            result = await rate_service.get_rate_for_pair("RUB", "USD")

            assert result == sample_rate_data
            mock_client.get_rate_by_symbol.assert_called_once_with("RUB/USD")

    async def test_get_rate_for_pair_tries_reverse(
        self, rate_service: RateService, sample_rate_data: RapiraRateData
    ) -> None:
        """Test that service tries reverse pair if direct pair fails."""
        with patch.object(rate_service, "get_api_client") as mock_get_client:
            # Create one mock client that will be reused
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # First call returns None (not found), second returns data
            mock_client.get_rate_by_symbol.side_effect = [
                None,  # Direct pair not found
                sample_rate_data,  # Reverse pair found
            ]

            mock_get_client.return_value = mock_client

            result = await rate_service.get_rate_for_pair("RUB", "USD")

            assert result == sample_rate_data
            assert mock_get_client.call_count == 2
            assert mock_client.get_rate_by_symbol.call_count == 2
            # Check that both symbols were tried
            calls = mock_client.get_rate_by_symbol.call_args_list
            assert calls[0][0][0] == "RUB/USD"
            assert calls[1][0][0] == "USD/RUB"

    async def test_get_rate_for_pair_not_found(self, rate_service: RateService) -> None:
        """Test rate retrieval when pair not found."""
        with patch.object(rate_service, "get_api_client") as mock_get_client:
            # Create one mock client that will be reused
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Both calls return None (not found)
            mock_client.get_rate_by_symbol.side_effect = [
                None,  # Direct pair not found
                None,  # Reverse pair not found
            ]

            mock_get_client.return_value = mock_client

            result = await rate_service.get_rate_for_pair("RUB", "USD")

            assert result is None
            assert mock_get_client.call_count == 2
            assert mock_client.get_rate_by_symbol.call_count == 2
            # Check that both symbols were tried
            calls = mock_client.get_rate_by_symbol.call_args_list
            assert calls[0][0][0] == "RUB/USD"
            assert calls[1][0][0] == "USD/RUB"

    async def test_apply_markup_to_rate_with_configured_pair(
        self, rate_service: RateService, sample_rate_data: RapiraRateData
    ) -> None:
        """Test markup application with configured currency pair."""
        result = await rate_service.apply_markup_to_rate(sample_rate_data, "RUB", "USD")

        expected_markup = 2.5  # From settings fixture
        expected_multiplier = 1.025
        expected_marked_up_rate = sample_rate_data.close * expected_multiplier

        assert result["symbol"] == "RUB/USD"
        assert result["original_rate"] == sample_rate_data.close
        assert result["marked_up_rate"] == expected_marked_up_rate
        assert result["markup_percentage"] == expected_markup
        assert result["base_currency"] == "RUB"
        assert result["quote_currency"] == "USD"
        assert result["change_24h"] == sample_rate_data.change_percentage
        assert result["is_positive_change"] == sample_rate_data.is_positive_change

    async def test_apply_markup_to_rate_with_default_markup(
        self, rate_service: RateService, sample_rate_data: RapiraRateData
    ) -> None:
        """Test markup application with default markup rate."""
        result = await rate_service.apply_markup_to_rate(sample_rate_data, "BTC", "ETH")

        expected_markup = rate_service.settings.default_markup_rate
        expected_multiplier = 1 + (expected_markup / 100)
        expected_marked_up_rate = sample_rate_data.close * expected_multiplier

        assert result["markup_percentage"] == expected_markup
        assert result["marked_up_rate"] == expected_marked_up_rate

    async def test_format_rate_message_positive_change(
        self, rate_service: RateService
    ) -> None:
        """Test rate message formatting with positive change."""
        rate_info = {
            "symbol": "RUB/USD",
            "base_currency": "RUB",
            "quote_currency": "USD",
            "marked_up_rate": 0.0106,
            "markup_percentage": 2.5,
            "change_24h": 1.5,
            "is_positive_change": True,
        }

        result = await rate_service.format_rate_message(rate_info)

        assert "💱" in result and "Курс валют" in result
        assert "RUB/USD" in result
        assert "0.010600" in result
        assert "2.5%" in result
        assert "📈" in result
        assert "+1.50%" in result

    async def test_format_rate_message_negative_change(
        self, rate_service: RateService
    ) -> None:
        """Test rate message formatting with negative change."""
        rate_info = {
            "symbol": "RUB/USD",
            "base_currency": "RUB",
            "quote_currency": "USD",
            "marked_up_rate": 1250.75,
            "markup_percentage": 3.0,
            "change_24h": -2.3,
            "is_positive_change": False,
        }

        result = await rate_service.format_rate_message(rate_info)

        assert "1,250.75" in result
        assert "3.0%" in result
        assert "📉" in result
        assert "-2.30%" in result

    async def test_format_rate_message_high_value(
        self, rate_service: RateService
    ) -> None:
        """Test rate message formatting with high value rates."""
        rate_info = {
            "symbol": "USD/RUB",
            "base_currency": "USD",
            "quote_currency": "RUB",
            "marked_up_rate": 95432.18,
            "markup_percentage": 2.0,
            "change_24h": 0.5,
            "is_positive_change": True,
        }

        result = await rate_service.format_rate_message(rate_info)

        assert "95,432.18" in result

    async def test_format_rate_message_small_value(
        self, rate_service: RateService
    ) -> None:
        """Test rate message formatting with small value rates."""
        rate_info = {
            "symbol": "RUB/BTC",
            "base_currency": "RUB",
            "quote_currency": "BTC",
            "marked_up_rate": 0.000001234,
            "markup_percentage": 1.5,
            "change_24h": -0.1,
            "is_positive_change": False,
        }

        result = await rate_service.format_rate_message(rate_info)

        assert "0.000001" in result

    async def test_cleanup(self, rate_service: RateService) -> None:
        """Test service cleanup."""
        mock_client = AsyncMock()
        rate_service._api_client = mock_client

        await rate_service.cleanup()

        mock_client.close.assert_called_once()
        assert rate_service._api_client is None

    async def test_cleanup_no_client(self, rate_service: RateService) -> None:
        """Test cleanup when no client exists."""
        rate_service._api_client = None

        await rate_service.cleanup()  # Should not raise


class TestRateHandlers:
    """Test cases for rate command handlers."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        settings = Settings()
        settings.add_currency_pair("RUB", "USD", markup_rate=2.5)
        return settings

    @pytest.fixture
    def mock_message(self) -> Message:
        """Create mock message."""
        message = MagicMock(spec=Message)
        message.answer = AsyncMock()
        return message

    @pytest.fixture
    def mock_callback(self) -> CallbackQuery:
        """Create mock callback query."""
        callback = MagicMock(spec=CallbackQuery)
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.data = "currency:RUB:USD"
        return callback

    async def test_cmd_rate_success(
        self, mock_message: Message, settings: Settings
    ) -> None:
        """Test successful /rate command handling."""
        with patch("src.bot.handlers.rate_handler.get_rate_keyboard") as mock_keyboard:
            mock_keyboard.return_value = MagicMock()

            await cmd_rate(mock_message, settings)

            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args
            assert "Выберите валютную пару" in call_args[0][0]
            assert call_args[1]["parse_mode"] == "HTML"
            mock_keyboard.assert_called_once_with(settings)

    async def test_cmd_rate_error(
        self, mock_message: Message, settings: Settings
    ) -> None:
        """Test /rate command error handling."""
        with patch(
            "src.bot.handlers.rate_handler.get_rate_keyboard",
            side_effect=Exception("Test error"),
        ):
            await cmd_rate(mock_message, settings)

            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args
            assert "Произошла ошибка" in call_args[0][0]

    async def test_handle_currency_selection_success(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test successful currency selection handling."""
        sample_rate_data = RapiraRateData(
            symbol="RUB/USD",
            open=0.0105,
            high=0.0107,
            low=0.0104,
            close=0.0106,
            chg=0.0095,
            change=0.0001,
            fee=0.001,
            lastDayClose=0.0105,
            usdRate=0.0106,
            baseUsdRate=0.0106,
            askPrice=0.0107,
            bidPrice=0.0105,
            baseCoinScale=2,
            coinScale=4,
            quoteCurrencyName="US Dollar",
            baseCurrency="RUB",
            quoteCurrency="USD",
        )

        with patch(
            "src.bot.handlers.rate_handler.get_rate_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_rate_for_pair.return_value = sample_rate_data
            mock_service.apply_markup_to_rate.return_value = {
                "symbol": "RUB/USD",
                "base_currency": "RUB",
                "quote_currency": "USD",
                "marked_up_rate": 0.0106,
                "markup_percentage": 2.5,
                "change_24h": 0.95,
                "is_positive_change": True,
            }
            mock_service.format_rate_message.return_value = "Test message"
            mock_get_service.return_value = mock_service

            await handle_currency_selection(mock_callback, settings)

            mock_callback.answer.assert_called_once_with(
                "🔄 Загружаю курс...", show_alert=False
            )
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert call_args[0][0] == "Test message"

    async def test_handle_currency_selection_invalid_callback(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test currency selection with invalid callback data."""
        mock_callback.data = "invalid:data"

        with patch("src.bot.handlers.rate_handler.parse_callback", return_value=None):
            await handle_currency_selection(mock_callback, settings)

            mock_callback.answer.assert_called_once_with(
                "❌ Неверный формат данных", show_alert=True
            )

    async def test_handle_currency_selection_wrong_action(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test currency selection with wrong action."""
        mock_callback.data = "wrong:RUB:USD"

        with patch(
            "src.bot.handlers.rate_handler.parse_callback",
            return_value=("wrong", "RUB", "USD"),
        ):
            await handle_currency_selection(mock_callback, settings)

            mock_callback.answer.assert_called_once_with(
                "❌ Неверное действие", show_alert=True
            )

    async def test_handle_currency_selection_rate_not_found(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test currency selection when rate not found."""
        with patch(
            "src.bot.handlers.rate_handler.get_rate_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_rate_for_pair.return_value = None
            mock_get_service.return_value = mock_service

            await handle_currency_selection(mock_callback, settings)

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "Курс не найден" in call_args[0][0]

    async def test_handle_currency_selection_api_error(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test currency selection with API error."""
        with patch(
            "src.bot.handlers.rate_handler.get_rate_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_rate_for_pair.side_effect = RapiraApiException("API Error")
            mock_get_service.return_value = mock_service

            await handle_currency_selection(mock_callback, settings)

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "Произошла ошибка" in call_args[0][0]

    async def test_handle_currency_selection_timeout_error(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test currency selection with timeout error."""
        with patch(
            "src.bot.handlers.rate_handler.get_rate_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_rate_for_pair.side_effect = asyncio.TimeoutError()
            mock_get_service.return_value = mock_service

            await handle_currency_selection(mock_callback, settings)

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "Превышено время ожидания" in call_args[0][0]

    async def test_handle_currency_selection_unexpected_error(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test currency selection with unexpected error."""
        with patch(
            "src.bot.handlers.rate_handler.get_rate_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_rate_for_pair.side_effect = ValueError("Unexpected error")
            mock_get_service.return_value = mock_service

            await handle_currency_selection(mock_callback, settings)

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "Произошла ошибка" in call_args[0][0]

    async def test_handle_back_to_rate_selection_success(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test successful back to rate selection handling."""
        with patch("src.bot.handlers.rate_handler.get_rate_keyboard") as mock_keyboard:
            mock_keyboard.return_value = MagicMock()

            await handle_back_to_rate_selection(mock_callback, settings)

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "Выберите валютную пару" in call_args[0][0]
            mock_callback.answer.assert_called_once()

    async def test_handle_back_to_rate_selection_error(
        self, mock_callback: CallbackQuery, settings: Settings
    ) -> None:
        """Test back to rate selection error handling."""
        with patch(
            "src.bot.handlers.rate_handler.get_rate_keyboard",
            side_effect=Exception("Test error"),
        ):
            await handle_back_to_rate_selection(mock_callback, settings)

            mock_callback.answer.assert_called_once_with(
                "❌ Произошла ошибка", show_alert=True
            )


class TestGlobalFunctions:
    """Test cases for global functions."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings()

    def test_get_rate_service_creates_instance(self, settings: Settings) -> None:
        """Test that get_rate_service creates new instance."""
        # Clear global instance
        import src.bot.handlers.rate_handler

        src.bot.handlers.rate_handler._rate_service = None

        service = get_rate_service(settings)

        assert isinstance(service, RateService)
        assert service.settings == settings

    def test_get_rate_service_reuses_instance(self, settings: Settings) -> None:
        """Test that get_rate_service reuses existing instance."""
        service1 = get_rate_service(settings)
        service2 = get_rate_service(settings)

        assert service1 is service2


class TestIntegration:
    """Integration tests for rate handler functionality."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings with multiple currency pairs."""
        settings = Settings()
        settings.add_currency_pair("RUB", "USD", markup_rate=2.5)
        settings.add_currency_pair("USDT", "RUB", markup_rate=3.0)
        settings.add_currency_pair("EUR", "USD", markup_rate=1.5)
        return settings

    async def test_full_rate_flow(self, settings: Settings) -> None:
        """Test complete rate request flow."""
        # Create sample rate data
        sample_rate_data = RapiraRateData(
            symbol="RUB/USD",
            open=0.0105,
            high=0.0107,
            low=0.0104,
            close=0.0106,
            chg=0.0095,
            change=0.0001,
            fee=0.001,
            lastDayClose=0.0105,
            usdRate=0.0106,
            baseUsdRate=0.0106,
            askPrice=0.0107,
            bidPrice=0.0105,
            baseCoinScale=2,
            coinScale=4,
            quoteCurrencyName="US Dollar",
            baseCurrency="RUB",
            quoteCurrency="USD",
        )

        # Create rate service
        rate_service = RateService(settings)

        # Mock API client
        with patch.object(rate_service, "get_api_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_rate_by_symbol.return_value = sample_rate_data
            mock_get_client.return_value = mock_client

            # Test the complete flow
            rate_data = await rate_service.get_rate_for_pair("RUB", "USD")
            assert rate_data == sample_rate_data

            rate_info = await rate_service.apply_markup_to_rate(rate_data, "RUB", "USD")
            assert rate_info["markup_percentage"] == 2.5
            assert rate_info["marked_up_rate"] == sample_rate_data.close * 1.025

            message = await rate_service.format_rate_message(rate_info)
            assert "RUB/USD" in message
            assert "2.5%" in message

            await rate_service.cleanup()

    async def test_error_recovery_flow(self, settings: Settings) -> None:
        """Test error recovery in rate request flow."""
        rate_service = RateService(settings)

        # Mock API client that fails first, then succeeds
        with patch.object(rate_service, "get_api_client") as mock_get_client:
            # Create one mock client that will be reused
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # First call fails, second succeeds with reverse pair
            sample_rate_data = RapiraRateData(
                symbol="USD/RUB",
                open=94.5,
                high=95.2,
                low=94.1,
                close=94.8,
                chg=0.003,
                change=0.3,
                fee=0.001,
                lastDayClose=94.5,
                usdRate=94.8,
                baseUsdRate=1.0,
                askPrice=95.0,
                bidPrice=94.6,
                baseCoinScale=2,
                coinScale=2,
                quoteCurrencyName="Russian Ruble",
                baseCurrency="USD",
                quoteCurrency="RUB",
            )

            # First call returns None (not found), second returns data
            mock_client.get_rate_by_symbol.side_effect = [
                None,  # Direct pair not found
                sample_rate_data,  # Reverse pair found
            ]

            mock_get_client.return_value = mock_client

            rate_data = await rate_service.get_rate_for_pair("RUB", "USD")
            assert rate_data == sample_rate_data
            assert mock_get_client.call_count == 2
            assert mock_client.get_rate_by_symbol.call_count == 2
            # Check that both symbols were tried
            calls = mock_client.get_rate_by_symbol.call_args_list
            assert calls[0][0][0] == "RUB/USD"
            assert calls[1][0][0] == "USD/RUB"
