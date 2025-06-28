"""Rate command handler for the crypto bot.

This module provides handlers for the /rate command, allowing users to view
exchange rates for supported currency pairs with applied markup rates.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.currency_keyboard import (
    CurrencyKeyboard,
    get_rate_keyboard,
    parse_callback,
)
from config.models import Settings
from models.rapira_models import RapiraRateData
from services.rapira_client import (
    RapiraApiClient,
    RapiraClientFactory,
    RapiraApiException,
)

# Create router for rate handlers
rate_router = Router(name="rate_handlers")


class RateService:
    """Service for handling rate-related operations."""

    def __init__(self, settings: Settings):
        """Initialize rate service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._api_client: RapiraApiClient | None = None

    async def get_api_client(self) -> RapiraApiClient:
        """Get or create API client.

        Returns:
            Configured Rapira API client
        """
        if self._api_client is None:
            self._api_client = RapiraClientFactory.create_from_settings(self.settings)
        return self._api_client

    async def get_rate_for_pair(self, base: str, quote: str) -> RapiraRateData | None:
        """Get rate data for a specific currency pair.

        Args:
            base: Base currency code
            quote: Quote currency code

        Returns:
            Rate data or None if not found
        """
        symbol = f"{base}/{quote}"

        try:
            client = await self.get_api_client()
            async with client:
                rate_data = await client.get_rate_by_symbol(symbol)
                return rate_data
        except RapiraApiException:
            # If direct pair not found, try reverse pair
            reverse_symbol = f"{quote}/{base}"
            try:
                client = await self.get_api_client()
                async with client:
                    rate_data = await client.get_rate_by_symbol(reverse_symbol)
                    return rate_data
            except RapiraApiException:
                return None

    async def apply_markup_to_rate(
        self, rate_data: RapiraRateData, base: str, quote: str
    ) -> dict[str, Any]:
        """Apply markup to rate data and format for display.

        Args:
            rate_data: Raw rate data from API
            base: Base currency code
            quote: Quote currency code

        Returns:
            Formatted rate data with markup applied
        """
        # Get markup rate from settings
        pair_string = f"{base}/{quote}"
        currency_pair = self.settings.get_currency_pair(pair_string)
        markup_rate = (
            currency_pair.markup_rate
            if currency_pair
            else self.settings.default_markup_rate
        )

        # Calculate markup
        markup_multiplier = 1 + (markup_rate / 100)

        # Apply markup to relevant prices
        marked_up_close = rate_data.close * markup_multiplier
        marked_up_ask = rate_data.ask_price * markup_multiplier
        marked_up_bid = rate_data.bid_price * markup_multiplier

        return {
            "symbol": f"{base}/{quote}",
            "original_rate": rate_data.close,
            "marked_up_rate": marked_up_close,
            "markup_percentage": markup_rate,
            "ask_price": marked_up_ask,
            "bid_price": marked_up_bid,
            "change_24h": rate_data.change_percentage,
            "is_positive_change": rate_data.is_positive_change,
            "base_currency": base,
            "quote_currency": quote,
            "spread": marked_up_ask - marked_up_bid,
            "last_updated": rate_data.base_currency,  # Using as placeholder for timestamp
        }

    async def format_rate_message(self, rate_info: dict[str, Any]) -> str:
        """Format rate information into a user-friendly message.

        Args:
            rate_info: Rate information with markup applied

        Returns:
            Formatted message string
        """
        symbol = rate_info["symbol"]
        base = rate_info["base_currency"]
        quote = rate_info["quote_currency"]
        rate = rate_info["marked_up_rate"]
        markup = rate_info["markup_percentage"]
        change = rate_info["change_24h"]
        is_positive = rate_info["is_positive_change"]

        # Format change indicator
        change_emoji = "📈" if is_positive else "📉"
        change_sign = "+" if is_positive else ""

        # Format rate with appropriate decimal places
        if rate >= 1000:
            rate_str = f"{rate:,.2f}"
        elif rate >= 1:
            rate_str = f"{rate:.4f}"
        else:
            rate_str = f"{rate:.6f}"

        message = f"""
💱 <b>Курс валют</b>

<b>{symbol}</b>
💰 Курс: <code>{rate_str}</code> {quote}
📊 Наценка: <code>{markup}%</code>
{change_emoji} Изменение 24ч: <code>{change_sign}{change:.2f}%</code>

<i>Курс указан с учетом наценки</i>
        """.strip()

        return message

    async def cleanup(self) -> None:
        """Cleanup service resources."""
        if self._api_client:
            await self._api_client.close()
            self._api_client = None


# Global rate service instance
_rate_service: RateService | None = None


def get_rate_service(settings: Settings) -> RateService:
    """Get or create rate service instance.

    Args:
        settings: Application settings

    Returns:
        Rate service instance
    """
    global _rate_service
    if _rate_service is None:
        _rate_service = RateService(settings)
    return _rate_service


@rate_router.message(Command("rate"))
async def cmd_rate(message: Message, settings: Settings) -> None:
    """Handle /rate command - show currency selection keyboard.

    Args:
        message: Incoming message
        settings: Application settings
    """
    try:
        # Create currency selection keyboard
        keyboard = get_rate_keyboard(settings)

        await message.answer(
            "💱 <b>Выберите валютную пару</b>\n\n"
            "Выберите валютную пару для просмотра текущего курса:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    except Exception as e:
        await message.answer(
            "❌ Произошла ошибка при загрузке списка валют. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="HTML",
        )
        # Log error for debugging
        print(f"Error in cmd_rate: {e}")


@rate_router.callback_query(F.data.startswith("currency:"))
async def handle_currency_selection(
    callback: CallbackQuery, settings: Settings
) -> None:
    """Handle currency pair selection from inline keyboard.

    Args:
        callback: Callback query from inline keyboard
        settings: Application settings
    """
    try:
        # Parse callback data
        parsed = parse_callback(callback.data)
        if not parsed:
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return

        action, base, quote = parsed

        if action != "currency":
            await callback.answer("❌ Неверное действие", show_alert=True)
            return

        # Show loading message
        await callback.answer("🔄 Загружаю курс...", show_alert=False)

        # Get rate service
        rate_service = get_rate_service(settings)

        # Fetch rate data
        rate_data = await rate_service.get_rate_for_pair(base, quote)

        if not rate_data:
            await callback.message.edit_text(
                f"❌ <b>Курс не найден</b>\n\n"
                f"К сожалению, курс для пары <code>{base}/{quote}</code> "
                f"в данный момент недоступен.\n\n"
                f"Попробуйте выбрать другую валютную пару или повторите попытку позже.",
                parse_mode="HTML",
                reply_markup=CurrencyKeyboard.create_back_keyboard(
                    "back_to_rate_selection"
                ),
            )
            return

        # Apply markup and format
        rate_info = await rate_service.apply_markup_to_rate(rate_data, base, quote)
        formatted_message = await rate_service.format_rate_message(rate_info)

        # Update message with rate information
        await callback.message.edit_text(
            formatted_message,
            parse_mode="HTML",
            reply_markup=CurrencyKeyboard.create_back_keyboard(
                "back_to_rate_selection"
            ),
        )

    except RapiraApiException as e:
        await callback.message.edit_text(
            "❌ <b>Ошибка API</b>\n\n"
            "Не удалось получить данные с биржи. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=CurrencyKeyboard.create_back_keyboard(
                "back_to_rate_selection"
            ),
        )
        print(f"API error in handle_currency_selection: {e}")

    except asyncio.TimeoutError:
        await callback.message.edit_text(
            "⏱️ <b>Превышено время ожидания</b>\n\n"
            "Запрос занял слишком много времени. "
            "Попробуйте еще раз.",
            parse_mode="HTML",
            reply_markup=CurrencyKeyboard.create_back_keyboard(
                "back_to_rate_selection"
            ),
        )

    except Exception as e:
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось получить курс валют. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=CurrencyKeyboard.create_back_keyboard(
                "back_to_rate_selection"
            ),
        )
        print(f"Unexpected error in handle_currency_selection: {e}")


@rate_router.callback_query(F.data == "back_to_rate_selection")
async def handle_back_to_rate_selection(
    callback: CallbackQuery, settings: Settings
) -> None:
    """Handle back button to return to rate selection.

    Args:
        callback: Callback query
        settings: Application settings
    """
    try:
        # Create currency selection keyboard
        keyboard = get_rate_keyboard(settings)

        await callback.message.edit_text(
            "💱 <b>Выберите валютную пару</b>\n\n"
            "Выберите валютную пару для просмотра текущего курса:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        print(f"Error in handle_back_to_rate_selection: {e}")


# Export router for inclusion in main dispatcher
__all__ = ["rate_router", "RateService", "get_rate_service"]
