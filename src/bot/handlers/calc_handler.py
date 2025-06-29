"""Calculation command handler for the crypto bot.

This module provides handlers for the /calc command, allowing users to calculate
exchange amounts for supported currency pairs with FSM-based input flow.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message

from bot.keyboards.currency_keyboard import (
    CurrencyKeyboard,
    get_calc_keyboard,
    parse_callback,
)
from bot.states.calc_states import CalcStates, CalcData
from config.models import Settings
from models.rapira_models import RapiraRateData
from services.calculation_service import (
    CalculationService,
    CalculationInput,
    CalculationResult,
    CalculationError,
    InvalidAmountError,
    UnsupportedPairError,
    RateDataError,
)
from services.notification_service import (
    NotificationService,
    NotificationData,
    NotificationError,
)
from services.rapira_client import (
    RapiraApiClient,
    RapiraClientFactory,
    RapiraApiException,
)

logger = logging.getLogger(__name__)


class CalcService:
    """Service for handling calculation-related operations."""

    def __init__(self, settings: Settings):
        """Initialize calculation service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._api_client: Optional[RapiraApiClient] = None
        self._calculation_service: Optional[CalculationService] = None
        self._notification_service: Optional[NotificationService] = None

    async def get_api_client(self) -> RapiraApiClient:
        """Get or create API client.

        Returns:
            Configured Rapira API client
        """
        if self._api_client is None:
            self._api_client = RapiraClientFactory.create_from_settings(self.settings)
        return self._api_client

    async def get_calculation_service(self) -> CalculationService:
        """Get or create calculation service.

        Returns:
            Calculation service instance
        """
        if self._calculation_service is None:
            self._calculation_service = CalculationService(self.settings)
            await self._calculation_service.initialize()
        return self._calculation_service

    async def get_notification_service(self, bot) -> NotificationService:
        """Get or create notification service.

        Args:
            bot: Telegram bot instance

        Returns:
            Notification service instance
        """
        if self._notification_service is None:
            self._notification_service = NotificationService(self.settings, bot)
            await self._notification_service.initialize()
        return self._notification_service

    async def get_rate_for_pair(
        self, base: str, quote: str
    ) -> Optional[RapiraRateData]:
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
                if rate_data is not None:
                    return rate_data
        except RapiraApiException:
            pass  # Continue to try reverse pair
        except Exception as e:
            logger.error(f"Error getting rate for {symbol}: {e}")
            return None

        # If direct pair not found, try reverse pair
        reverse_symbol = f"{quote}/{base}"
        try:
            client = await self.get_api_client()
            async with client:
                rate_data = await client.get_rate_by_symbol(reverse_symbol)
                return rate_data
        except Exception as e:
            logger.error(f"Error getting reverse rate for {reverse_symbol}: {e}")
            return None

    async def calculate_exchange(
        self, base: str, quote: str, amount: Decimal, rate_data: RapiraRateData
    ) -> CalculationResult:
        """Calculate currency exchange.

        Args:
            base: Base currency code
            quote: Quote currency code
            amount: Amount to convert
            rate_data: Market rate data

        Returns:
            Calculation result

        Raises:
            CalculationError: If calculation fails
        """
        calc_service = await self.get_calculation_service()

        calc_input = CalculationInput(
            base_currency=base,
            quote_currency=quote,
            amount=amount,
            rate_data=rate_data,
        )

        return await calc_service.calculate_exchange(calc_input)

    async def send_manager_notification(
        self, calculation_result: CalculationResult, user_info: Dict[str, Any], bot
    ) -> bool:
        """Send notification to assigned manager.

        Args:
            calculation_result: Calculation result data
            user_info: User information
            bot: Telegram bot instance

        Returns:
            True if notification sent successfully
        """
        try:
            notification_service = await self.get_notification_service(bot)

            # Create notification data
            import uuid

            transaction_id = str(uuid.uuid4())[:8]  # Short transaction ID

            notification_data = NotificationData(
                transaction_id=transaction_id,
                user_id=user_info.get("user_id", 0),
                username=user_info.get("username"),
                full_name=user_info.get("full_name"),
                calculation_result=calculation_result,
            )

            # Send notification
            await notification_service.send_transaction_notification(notification_data)
            return True

        except NotificationError as e:
            logger.error(f"Failed to send manager notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False

    async def cleanup(self) -> None:
        """Cleanup service resources."""
        if self._api_client:
            await self._api_client.close()
            self._api_client = None
        if self._calculation_service:
            await self._calculation_service.cleanup()
            self._calculation_service = None
        if self._notification_service:
            await self._notification_service.cleanup()
            self._notification_service = None


# Global calc service instance
_calc_service: Optional[CalcService] = None


def get_calc_service(settings: Settings) -> CalcService:
    """Get or create calc service instance.

    Args:
        settings: Application settings

    Returns:
        Calc service instance
    """
    global _calc_service
    if _calc_service is None:
        _calc_service = CalcService(settings)
    return _calc_service


async def format_calculation_result(
    result: CalculationResult, confirmed: bool = False
) -> str:
    """Format calculation result for display.

    Args:
        result: Calculation result
        confirmed: Whether calculation is confirmed

    Returns:
        Formatted message string
    """
    status_emoji = "✅" if confirmed else "🧮"
    status_text = "Подтвержденный расчет" if confirmed else "Результат расчета"

    # Format change indicator
    change_emoji = "📈" if result.markup_rate > 0 else "📊"

    message = f"""
{status_emoji} <b>{status_text}</b>

💱 <b>Валютная пара:</b> {result.base_currency} → {result.quote_currency}

💰 <b>Сумма обмена:</b>
• Вы отдаете: <code>{result.formatted_input}</code>
• Вы получаете: <code>{result.formatted_output}</code>

📊 <b>Курс и комиссии:</b>
• Рыночный курс: <code>{result.market_rate:.6f}</code>
• Наша наценка: <code>{result.markup_rate}%</code>
• Итоговый курс: <code>{result.final_rate:.6f}</code>

{change_emoji} <b>Наша прибыль:</b> <code>{result.markup_amount:.2f} {result.quote_currency}</code>
    """.strip()

    if not confirmed:
        message += "\n\n<i>Подтвердите расчет для отправки заявки менеджеру</i>"

    return message


def create_calc_router() -> Router:
    """Create and configure calc handlers router.

    Returns:
        Configured router with calc handlers
    """
    router = Router(name="calc_handlers")

    @router.message(Command("calc"))
    async def cmd_calc(message: Message, state: FSMContext, settings: Settings) -> None:
        """Handle /calc command - start calculation flow.

        Args:
            message: Incoming message
            state: FSM context
            settings: Application settings
        """
        try:
            # Clear any existing state
            await state.clear()

            # Store user information
            await state.update_data(
                {
                    CalcData.USER_ID: message.from_user.id,
                    CalcData.USERNAME: message.from_user.username or "Unknown",
                    CalcData.MESSAGE_ID: message.message_id,
                }
            )

            # Create currency selection keyboard
            keyboard = get_calc_keyboard(settings)

            # Send selection message
            sent_message = await message.answer(
                "🧮 <b>Калькулятор обмена</b>\n\n" "Выберите валютную пару для расчета:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            # Update message ID and set state
            await state.update_data({CalcData.MESSAGE_ID: sent_message.message_id})
            await state.set_state(CalcStates.selecting_pair)

        except Exception as e:
            logger.error(f"Error in cmd_calc: {e}")
            await message.answer(
                "❌ Произошла ошибка при запуске калькулятора. "
                "Попробуйте позже или обратитесь к администратору.",
                parse_mode="HTML",
            )

    return router


# Export router for inclusion in main dispatcher
__all__ = ["create_calc_router", "CalcService", "get_calc_service"]
