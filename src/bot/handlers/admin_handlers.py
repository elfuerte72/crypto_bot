"""Administrative command handlers for the crypto bot.

This module provides handlers for administrative commands like setting markup rates,
managing currency pairs, and other admin-only operations.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.currency_keyboard import (
    CurrencyKeyboard,
    parse_callback,
)
from config.models import Settings


# Create router for admin handlers
admin_router = Router(name="admin_handlers")


class AdminStates(StatesGroup):
    """FSM states for admin operations."""

    waiting_for_markup_value = State()


class AdminService:
    """Service for handling admin-related operations."""

    def __init__(self, settings: Settings):
        """Initialize admin service.

        Args:
            settings: Application settings
        """
        self.settings = settings

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an administrator.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is admin, False otherwise
        """
        return user_id in self.settings.telegram.admin_user_ids

    def get_current_markup(self, pair_string: str) -> float:
        """Get current markup rate for currency pair.

        Args:
            pair_string: Currency pair string (e.g., 'USD/RUB')

        Returns:
            Current markup rate percentage
        """
        currency_pair = self.settings.get_currency_pair(pair_string)
        if currency_pair:
            return currency_pair.markup_rate
        return self.settings.default_markup_rate

    def update_markup_rate(self, pair_string: str, markup_rate: float) -> bool:
        """Update markup rate for currency pair.

        Args:
            pair_string: Currency pair string
            markup_rate: New markup rate percentage

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Validate markup rate
            if not (0.0 <= markup_rate <= 100.0):
                return False

            # Update existing pair or create new one
            if pair_string in self.settings.currency_pairs:
                self.settings.currency_pairs[pair_string].markup_rate = markup_rate
            else:
                # Parse pair string to base and quote
                parts = pair_string.split("/")
                if len(parts) != 2:
                    return False

                base, quote = parts
                self.settings.add_currency_pair(
                    base=base.upper(), quote=quote.upper(), markup_rate=markup_rate
                )

            return True
        except Exception:
            return False

    def format_markup_info_message(self) -> str:
        """Format markup information for all currency pairs.

        Returns:
            Formatted message with current markup rates
        """
        message = "⚙️ <b>Текущие наценки</b>\n\n"

        if not self.settings.currency_pairs:
            message += "📝 Валютные пары не настроены\n"
            message += f"🔧 Наценка по умолчанию: <code>{self.settings.default_markup_rate}%</code>"
        else:
            for pair_string, pair_config in self.settings.currency_pairs.items():
                status_emoji = "✅" if pair_config.is_active else "❌"
                message += f"{status_emoji} <b>{pair_string}</b>: <code>{pair_config.markup_rate}%</code>\n"

            message += f"\n🔧 Наценка по умолчанию: <code>{self.settings.default_markup_rate}%</code>"

        message += "\n\n💡 <i>Выберите валютную пару для изменения наценки</i>"
        return message

    def format_markup_change_message(
        self, pair_string: str, old_markup: float, new_markup: float
    ) -> str:
        """Format markup change confirmation message.

        Args:
            pair_string: Currency pair string
            old_markup: Previous markup rate
            new_markup: New markup rate

        Returns:
            Formatted confirmation message
        """
        return f"""
✅ <b>Наценка обновлена</b>

💱 Валютная пара: <b>{pair_string}</b>
📊 Старая наценка: <code>{old_markup}%</code>
🆕 Новая наценка: <code>{new_markup}%</code>

<i>Изменения вступят в силу немедленно</i>
        """.strip()


# Global admin service instance
_admin_service: AdminService | None = None


def get_admin_service(settings: Settings) -> AdminService:
    """Get or create admin service instance.

    Args:
        settings: Application settings

    Returns:
        Admin service instance
    """
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService(settings)
    return _admin_service


async def check_admin_access(
    update: Message | CallbackQuery, settings: Settings
) -> bool:
    """Check if user has admin access.

    Args:
        update: Message or CallbackQuery
        settings: Application settings

    Returns:
        True if user is admin, False otherwise
    """
    admin_service = get_admin_service(settings)
    user_id = update.from_user.id if update.from_user else 0

    if not admin_service.is_admin(user_id):
        if isinstance(update, Message):
            await update.answer(
                "❌ <b>Доступ запрещен</b>\n\n"
                "У вас нет прав администратора для выполнения этой команды.",
                parse_mode="HTML",
            )
        elif isinstance(update, CallbackQuery):
            await update.answer("❌ Доступ запрещен", show_alert=True)
        return False

    return True


@admin_router.message(Command("set_markup"))
async def cmd_set_markup(message: Message, settings: Settings) -> None:
    """Handle /set_markup command - show currency pairs for markup management.

    Args:
        message: Incoming message
        settings: Application settings
    """
    # Check admin access
    if not await check_admin_access(message, settings):
        return

    try:
        admin_service = get_admin_service(settings)

        # Create markup selection keyboard
        keyboard = CurrencyKeyboard(settings)
        markup_keyboard = keyboard.create_markup_selection_keyboard()

        # Format message with current markup info
        markup_info = admin_service.format_markup_info_message()

        await message.answer(
            markup_info,
            reply_markup=markup_keyboard,
            parse_mode="HTML",
        )

    except Exception as e:
        await message.answer(
            "❌ Произошла ошибка при загрузке настроек наценки. "
            "Попробуйте позже или обратитесь к разработчику.",
            parse_mode="HTML",
        )
        # Log error for debugging
        print(f"Error in cmd_set_markup: {e}")


@admin_router.callback_query(F.data.startswith("markup:"))
async def handle_markup_selection(
    callback: CallbackQuery, settings: Settings, state: FSMContext
) -> None:
    """Handle currency pair selection for markup editing.

    Args:
        callback: Callback query from inline keyboard
        settings: Application settings
        state: FSM context for storing state data
    """
    # Check admin access
    if not await check_admin_access(callback, settings):
        return

    try:
        # Parse callback data
        parsed = parse_callback(callback.data)
        if not parsed:
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return

        action, base, quote = parsed

        if action != "markup":
            await callback.answer("❌ Неверное действие", show_alert=True)
            return

        pair_string = f"{base}/{quote}"
        admin_service = get_admin_service(settings)
        current_markup = admin_service.get_current_markup(pair_string)

        # Store pair info in FSM data
        await state.update_data(
            pair_string=pair_string,
            base_currency=base,
            quote_currency=quote,
            current_markup=current_markup,
        )

        # Set state for waiting markup value
        await state.set_state(AdminStates.waiting_for_markup_value)

        # Show markup input prompt
        await callback.message.edit_text(
            f"💱 <b>Изменение наценки</b>\n\n"
            f"Валютная пара: <b>{pair_string}</b>\n"
            f"Текущая наценка: <code>{current_markup}%</code>\n\n"
            f"📝 Введите новую наценку в процентах (0-100):\n"
            f"<i>Например: 2.5 или 5.0</i>",
            reply_markup=CurrencyKeyboard.create_back_keyboard(
                "back_to_markup_selection"
            ),
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        print(f"Error in handle_markup_selection: {e}")


@admin_router.message(AdminStates.waiting_for_markup_value)
async def handle_markup_value_input(
    message: Message, settings: Settings, state: FSMContext
) -> None:
    """Handle markup value input from admin.

    Args:
        message: Message with markup value
        settings: Application settings
        state: FSM context with stored data
    """
    # Check admin access
    if not await check_admin_access(message, settings):
        await state.clear()
        return

    try:
        # Get stored data
        data = await state.get_data()
        pair_string = data.get("pair_string")
        current_markup = data.get("current_markup", 0.0)

        if not pair_string:
            await message.answer(
                "❌ Ошибка: данные сессии потеряны. Начните заново с команды /set_markup",
                parse_mode="HTML",
            )
            await state.clear()
            return

        # Validate and parse markup value
        markup_text = message.text.strip().replace(",", ".")

        # Check for valid number format
        if not re.match(r"^\d+(\.\d+)?$", markup_text):
            await message.answer(
                "❌ <b>Неверный формат</b>\n\n"
                "Введите число от 0 до 100.\n"
                "Примеры: <code>2.5</code>, <code>5</code>, <code>10.75</code>",
                parse_mode="HTML",
            )
            return

        try:
            markup_rate = float(markup_text)
        except ValueError:
            await message.answer(
                "❌ <b>Неверный формат числа</b>\n\n"
                "Введите корректное число от 0 до 100.",
                parse_mode="HTML",
            )
            return

        # Validate range
        if not (0.0 <= markup_rate <= 100.0):
            await message.answer(
                "❌ <b>Значение вне диапазона</b>\n\n"
                "Наценка должна быть от 0% до 100%.\n"
                f"Вы ввели: <code>{markup_rate}%</code>",
                parse_mode="HTML",
            )
            return

        # Update markup rate
        admin_service = get_admin_service(settings)
        success = admin_service.update_markup_rate(pair_string, markup_rate)

        if not success:
            await message.answer(
                "❌ <b>Ошибка обновления</b>\n\n"
                "Не удалось сохранить новую наценку. "
                "Попробуйте еще раз или обратитесь к разработчику.",
                parse_mode="HTML",
            )
            return

        # Format success message
        success_message = admin_service.format_markup_change_message(
            pair_string, current_markup, markup_rate
        )

        # Send confirmation with back to main menu option
        keyboard = CurrencyKeyboard(settings)
        markup_keyboard = keyboard.create_markup_selection_keyboard()

        await message.answer(success_message, parse_mode="HTML")

        # Show updated markup list
        await asyncio.sleep(1)  # Small delay for better UX

        markup_info = admin_service.format_markup_info_message()
        await message.answer(
            markup_info, reply_markup=markup_keyboard, parse_mode="HTML"
        )

        # Clear FSM state
        await state.clear()

    except Exception as e:
        await message.answer(
            "❌ Произошла ошибка при обработке наценки. "
            "Попробуйте еще раз или обратитесь к разработчику.",
            parse_mode="HTML",
        )
        await state.clear()
        print(f"Error in handle_markup_value_input: {e}")


@admin_router.callback_query(F.data == "back_to_markup_selection")
async def handle_back_to_markup_selection(
    callback: CallbackQuery, settings: Settings, state: FSMContext
) -> None:
    """Handle back button to return to markup selection.

    Args:
        callback: Callback query
        settings: Application settings
        state: FSM context to clear
    """
    # Check admin access
    if not await check_admin_access(callback, settings):
        await state.clear()
        return

    try:
        # Clear any FSM state
        await state.clear()

        admin_service = get_admin_service(settings)

        # Create markup selection keyboard
        keyboard = CurrencyKeyboard(settings)
        markup_keyboard = keyboard.create_markup_selection_keyboard()

        # Format message with current markup info
        markup_info = admin_service.format_markup_info_message()

        await callback.message.edit_text(
            markup_info,
            reply_markup=markup_keyboard,
            parse_mode="HTML",
        )

        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        print(f"Error in handle_back_to_markup_selection: {e}")


# Export router for inclusion in main dispatcher
__all__ = [
    "admin_router",
    "AdminService",
    "get_admin_service",
    "AdminStates",
    "check_admin_access",
]
