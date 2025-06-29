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


async def handle_pair_selection(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    """Handle currency pair selection.

    Args:
        callback: Callback query
        state: FSM context
        settings: Application settings
    """
    try:
        await callback.answer()

        # Parse callback data
        callback_data = parse_callback(callback.data)
        if not callback_data or callback_data.action != "currency":
            await callback.message.edit_text(
                "❌ Неверные данные. Попробуйте еще раз.", parse_mode="HTML"
            )
            return

        base_currency = callback_data.base_currency
        quote_currency = callback_data.quote_currency

        # Store pair selection
        await state.update_data(
            {
                CalcData.BASE_CURRENCY: base_currency,
                CalcData.QUOTE_CURRENCY: quote_currency,
            }
        )

        # Request amount input
        await callback.message.edit_text(
            f"💰 <b>Ввод суммы</b>\n\n"
            f"Валютная пара: <code>{base_currency} → {quote_currency}</code>\n\n"
            f"Введите сумму в {base_currency} для расчета:",
            parse_mode="HTML",
        )

        await state.set_state(CalcStates.entering_amount)

    except Exception as e:
        logger.error(f"Error in handle_pair_selection: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при выборе валютной пары.", parse_mode="HTML"
        )


async def handle_amount_input(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    """Handle amount input.

    Args:
        message: Incoming message
        state: FSM context
        settings: Application settings
    """
    try:
        # Parse amount
        try:
            amount = Decimal(message.text.replace(",", "."))
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, InvalidOperation):
            await message.answer(
                "❌ Неверный формат суммы. Введите положительное число:",
                parse_mode="HTML",
            )
            return

        # Get state data
        data = await state.get_data()
        base_currency = data.get(CalcData.BASE_CURRENCY)
        quote_currency = data.get(CalcData.QUOTE_CURRENCY)

        if not base_currency or not quote_currency:
            await message.answer(
                "❌ Ошибка: не выбрана валютная пара. Начните сначала с /calc",
                parse_mode="HTML",
            )
            await state.clear()
            return

        # Get calc service and rate data
        calc_service = get_calc_service(settings)
        rate_data = await calc_service.get_rate_for_pair(base_currency, quote_currency)

        if not rate_data:
            await message.answer(
                f"❌ Курс для пары {base_currency}/{quote_currency} не найден.",
                parse_mode="HTML",
            )
            return

        # Calculate exchange
        calculation_result = await calc_service.calculate_exchange(
            base_currency, quote_currency, amount, rate_data
        )

        # Store calculation result
        await state.update_data({CalcData.CALCULATION_RESULT: calculation_result})

        # Format and send result
        result_message = await format_calculation_result(calculation_result)

        # Add confirmation keyboard
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить", callback_data="calc_confirm"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отменить", callback_data="calc_cancel"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="calc_back_to_pairs"
                    )
                ],
            ]
        )

        await message.answer(result_message, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(CalcStates.confirming_calculation)

    except Exception as e:
        logger.error(f"Error in handle_amount_input: {e}")
        await message.answer(
            "❌ Произошла ошибка при расчете. Попробуйте еще раз.", parse_mode="HTML"
        )


async def handle_calculation_confirmation(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    """Handle calculation confirmation.

    Args:
        callback: Callback query
        state: FSM context
        settings: Application settings
    """
    try:
        await callback.answer()

        # Get state data
        data = await state.get_data()
        calculation_result = data.get(CalcData.CALCULATION_RESULT)

        if not calculation_result:
            await callback.message.edit_text(
                "❌ Ошибка: данные расчета не найдены.", parse_mode="HTML"
            )
            await state.clear()
            return

        # Send manager notification
        calc_service = get_calc_service(settings)
        user_info = {
            "user_id": data.get(CalcData.USER_ID),
            "username": data.get(CalcData.USERNAME),
            "full_name": callback.from_user.full_name,
        }

        notification_sent = await calc_service.send_manager_notification(
            calculation_result, user_info, callback.bot
        )

        # Format confirmed result
        result_message = await format_calculation_result(
            calculation_result, confirmed=True
        )

        if notification_sent:
            result_message += "\n\n✅ <b>Заявка отправлена менеджеру!</b>"
        else:
            result_message += (
                "\n\n⚠️ <b>Заявка создана, но уведомление менеджеру не отправлено.</b>"
            )

        # Add new calculation button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🧮 Новый расчет", callback_data="calc_new")]
            ]
        )

        await callback.message.edit_text(
            result_message, reply_markup=keyboard, parse_mode="HTML"
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error in handle_calculation_confirmation: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при подтверждении расчета.", parse_mode="HTML"
        )


async def handle_calculation_cancellation(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    """Handle calculation cancellation.

    Args:
        callback: Callback query
        state: FSM context
        settings: Application settings
    """
    try:
        await callback.answer()

        await callback.message.edit_text(
            "❌ <b>Расчет отменен</b>\n\nИспользуйте /calc для нового расчета.",
            parse_mode="HTML",
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Error in handle_calculation_cancellation: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при отмене расчета.", parse_mode="HTML"
        )


async def handle_back_to_pair_selection(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    """Handle back to pair selection.

    Args:
        callback: Callback query
        state: FSM context
        settings: Application settings
    """
    try:
        await callback.answer()

        # Create currency selection keyboard
        keyboard = get_calc_keyboard(settings)

        # Send selection message
        await callback.message.edit_text(
            "🧮 <b>Калькулятор обмена</b>\n\n" "Выберите валютную пару для расчета:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(CalcStates.selecting_pair)

    except Exception as e:
        logger.error(f"Error in handle_back_to_pair_selection: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при возврате к выбору пары.", parse_mode="HTML"
        )


async def handle_new_calculation(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    """Handle new calculation request.

    Args:
        callback: Callback query
        state: FSM context
        settings: Application settings
    """
    try:
        await callback.answer()

        # Clear state and start new calculation
        await state.clear()

        # Create currency selection keyboard
        keyboard = get_calc_keyboard(settings)

        # Send selection message
        await callback.message.edit_text(
            "🧮 <b>Калькулятор обмена</b>\n\n" "Выберите валютную пару для расчета:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(CalcStates.selecting_pair)

    except Exception as e:
        logger.error(f"Error in handle_new_calculation: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании нового расчета.", parse_mode="HTML"
        )


def create_calc_router() -> Router:
    """Create and configure calc handlers router.

    Returns:
        Configured router with calc handlers
    """
    router = Router(name="calc_handlers")

    # Register handlers
    router.message.register(cmd_calc, Command("calc"))
    router.callback_query.register(
        handle_pair_selection, F.data.startswith("currency:"), CalcStates.selecting_pair
    )
    router.message.register(handle_amount_input, CalcStates.entering_amount)
    router.callback_query.register(
        handle_calculation_confirmation,
        F.data == "calc_confirm",
        CalcStates.confirming_calculation,
    )
    router.callback_query.register(
        handle_calculation_cancellation,
        F.data == "calc_cancel",
        CalcStates.confirming_calculation,
    )
    router.callback_query.register(
        handle_back_to_pair_selection,
        F.data == "calc_back_to_pairs",
        CalcStates.confirming_calculation,
    )
    router.callback_query.register(handle_new_calculation, F.data == "calc_new")

    return router


# Export all functions and classes
__all__ = [
    "create_calc_router",
    "CalcService",
    "get_calc_service",
    "cmd_calc",
    "handle_pair_selection",
    "handle_amount_input",
    "handle_calculation_confirmation",
    "handle_calculation_cancellation",
    "handle_back_to_pair_selection",
    "handle_new_calculation",
    "format_calculation_result",
]
