"""Notification service for Telegram messaging.

This module provides comprehensive notification functionality including message
formatting, rate alerts, calculation results, and admin notifications with
template-based formatting and error handling.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from pydantic import BaseModel, Field, field_validator

from config.models import ManagerConfig, Settings
from services.calculation_service import CalculationResult
from .base import BaseService

logger = logging.getLogger(__name__)


class NotificationData(BaseModel):
    """Data structure for notification content."""

    transaction_id: str = Field(..., description="Unique transaction identifier")
    user_id: int = Field(..., description="Telegram user ID who initiated transaction")
    username: str | None = Field(None, description="Username of the user")
    full_name: str | None = Field(None, description="Full name of the user")
    calculation_result: CalculationResult = Field(
        ..., description="Calculation result data"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Transaction timestamp"
    )
    additional_info: Dict[str, Any] = Field(
        default_factory=dict, description="Additional transaction information"
    )

    @field_validator("transaction_id")
    @classmethod
    def validate_transaction_id(cls, v: str) -> str:
        """Validate transaction ID format."""
        if not v or len(v) < 8:
            raise ValueError("Transaction ID must be at least 8 characters long")
        return v

    @property
    def user_display_name(self) -> str:
        """Get user display name for notifications."""
        if self.full_name:
            return self.full_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.user_id}"

    @property
    def currency_pair(self) -> str:
        """Get currency pair string."""
        return self.calculation_result.pair_string

    @property
    def formatted_timestamp(self) -> str:
        """Get formatted timestamp."""
        return self.timestamp.strftime("%d.%m.%Y %H:%M:%S UTC")


class NotificationTemplate(BaseModel):
    """Template for notification messages."""

    title: str = Field(..., description="Notification title")
    body_template: str = Field(..., description="Message body template")
    include_user_info: bool = Field(
        default=True, description="Include user information in notification"
    )
    include_calculation_details: bool = Field(
        default=True, description="Include detailed calculation information"
    )
    include_action_buttons: bool = Field(
        default=True, description="Include action buttons in notification"
    )

    def format_message(self, data: NotificationData) -> str:
        """Format notification message using template and data."""
        template_vars = {
            "transaction_id": data.transaction_id,
            "user_display_name": data.user_display_name,
            "user_id": data.user_id,
            "username": data.username or "N/A",
            "full_name": data.full_name or "N/A",
            "currency_pair": data.currency_pair,
            "input_amount": data.calculation_result.formatted_input,
            "output_amount": data.calculation_result.formatted_output,
            "exchange_rate": data.calculation_result.formatted_rate,
            "markup_rate": f"{data.calculation_result.markup_rate}%",
            "markup_amount": data.calculation_result.formatted_output.split()[0]
            if data.calculation_result.markup_amount
            else "0",
            "direction": data.calculation_result.calculation_direction.title(),
            "timestamp": data.formatted_timestamp,
            "base_currency": data.calculation_result.base_currency,
            "quote_currency": data.calculation_result.quote_currency,
        }

        try:
            return self.body_template.format(**template_vars)
        except KeyError as e:
            logger.error(f"Template formatting error: missing variable {e}")
            return f"Template error: {e}"


class NotificationResponse(BaseModel):
    """Response from notification sending."""

    success: bool = Field(..., description="Whether notification was sent successfully")
    message_id: int | None = Field(None, description="Telegram message ID if sent")
    manager_id: int = Field(..., description="Manager user ID")
    error_message: str | None = Field(None, description="Error message if failed")
    sent_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when sent"
    )

    @property
    def is_success(self) -> bool:
        """Check if notification was successful."""
        return self.success and self.message_id is not None


class NotificationError(Exception):
    """Base exception for notification errors."""

    def __init__(self, message: str, manager_id: int = 0, transaction_id: str = ""):
        super().__init__(message)
        self.message = message
        self.manager_id = manager_id
        self.transaction_id = transaction_id


class ManagerNotFoundError(NotificationError):
    """Manager not found for currency pair."""

    pass


class TemplateError(NotificationError):
    """Template formatting error."""

    pass


class TelegramDeliveryError(NotificationError):
    """Telegram message delivery error."""

    pass


class NotificationService(BaseService):
    """Service for sending transaction notifications to managers."""

    def __init__(self, settings: Settings, bot: Bot):
        """Initialize notification service.

        Args:
            settings: Application settings
            bot: Telegram bot instance
        """
        super().__init__(settings)
        self.bot = bot
        self._templates: Dict[str, NotificationTemplate] = {}
        self._initialize_templates()

    async def initialize(self) -> None:
        """Initialize notification service."""
        logger.info("Notification service initialized")

    async def cleanup(self) -> None:
        """Cleanup notification service resources."""
        logger.info("Notification service cleaned up")

    def _initialize_templates(self) -> None:
        """Initialize notification message templates."""
        # Transaction notification template
        self._templates["transaction"] = NotificationTemplate(
            title="💱 Новая транзакция",
            body_template="""🔔 <b>Новая заявка на обмен валют</b>

📋 <b>Детали транзакции:</b>
• ID: <code>{transaction_id}</code>
• Время: {timestamp}

👤 <b>Клиент:</b>
• Имя: {user_display_name}
• ID: <code>{user_id}</code>

💰 <b>Обмен:</b>
• Валютная пара: <b>{currency_pair}</b>
• Направление: {direction}
• Отдает: <b>{input_amount}</b>
• Получает: <b>{output_amount}</b>
• Курс: {exchange_rate}

📊 <b>Комиссия:</b>
• Наценка: {markup_rate}
• Прибыль: <b>{markup_amount} {quote_currency}</b>

❓ Подтвердите обработку заявки:""",
            include_user_info=True,
            include_calculation_details=True,
            include_action_buttons=True,
        )

        # Rate request notification template
        self._templates["rate_request"] = NotificationTemplate(
            title="📊 Запрос курса",
            body_template="""📊 <b>Запрос курса валют</b>

👤 <b>Клиент:</b>
• Имя: {user_display_name}
• ID: <code>{user_id}</code>

💱 <b>Запрос:</b>
• Валютная пара: <b>{currency_pair}</b>
• Время: {timestamp}

💰 <b>Текущий курс:</b>
• {exchange_rate}
• Наценка: {markup_rate}""",
            include_user_info=True,
            include_calculation_details=False,
            include_action_buttons=False,
        )

        # Error notification template
        self._templates["error"] = NotificationTemplate(
            title="⚠️ Ошибка системы",
            body_template="""⚠️ <b>Системная ошибка</b>

📋 <b>Детали:</b>
• ID транзакции: <code>{transaction_id}</code>
• Время: {timestamp}
• Ошибка: {error_message}

👤 <b>Пользователь:</b>
• {user_display_name} (ID: {user_id})

🔧 Требуется вмешательство администратора.""",
            include_user_info=True,
            include_calculation_details=False,
            include_action_buttons=False,
        )

    def _create_action_buttons(
        self, transaction_id: str, currency_pair: str
    ) -> InlineKeyboardMarkup:
        """Create action buttons for transaction notifications.

        Args:
            transaction_id: Transaction identifier
            currency_pair: Currency pair string

        Returns:
            Inline keyboard markup with action buttons
        """
        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm:{transaction_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{transaction_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏳ В обработке",
                    callback_data=f"processing:{transaction_id}",
                ),
                InlineKeyboardButton(
                    text="💬 Связаться",
                    callback_data=f"contact:{transaction_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Детали",
                    callback_data=f"details:{transaction_id}",
                ),
            ],
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def _get_manager_for_pair(self, currency_pair: str) -> ManagerConfig | None:
        """Get manager assigned to currency pair.

        Args:
            currency_pair: Currency pair string

        Returns:
            Manager configuration or None if not found
        """
        return self.settings.get_manager_for_pair(currency_pair)

    def _get_default_manager(self) -> ManagerConfig | None:
        """Get default manager if no specific manager assigned.

        Returns:
            Default manager configuration or None
        """
        if self.settings.default_manager_id:
            return self.settings.managers.get(self.settings.default_manager_id)
        return None

    def _get_all_active_managers(self) -> List[ManagerConfig]:
        """Get all active managers.

        Returns:
            List of active manager configurations
        """
        return self.settings.get_active_managers()

    async def send_transaction_notification(
        self,
        notification_data: NotificationData,
        template_name: str = "transaction",
    ) -> List[NotificationResponse]:
        """Send transaction notification to assigned managers.

        Args:
            notification_data: Transaction notification data
            template_name: Template name to use

        Returns:
            List of notification responses

        Raises:
            ManagerNotFoundError: If no manager found for currency pair
            TemplateError: If template formatting fails
        """
        try:
            # Get template
            template = self._templates.get(template_name)
            if not template:
                raise TemplateError(
                    f"Template '{template_name}' not found",
                    transaction_id=notification_data.transaction_id,
                )

            # Find managers for this currency pair
            managers = []
            pair_manager = self._get_manager_for_pair(notification_data.currency_pair)
            if pair_manager and pair_manager.notification_enabled:
                managers.append(pair_manager)
            else:
                # Try default manager
                default_manager = self._get_default_manager()
                if default_manager and default_manager.notification_enabled:
                    managers.append(default_manager)

            if not managers:
                raise ManagerNotFoundError(
                    f"No active manager found for pair {notification_data.currency_pair}",
                    transaction_id=notification_data.transaction_id,
                )

            # Send notifications to all assigned managers
            responses = []
            for manager in managers:
                try:
                    response = await self._send_notification_to_manager(
                        manager, notification_data, template
                    )
                    responses.append(response)
                    logger.info(
                        f"Notification sent to manager {manager.user_id} for transaction {notification_data.transaction_id}"
                    )
                except Exception as e:
                    error_response = NotificationResponse(
                        success=False,
                        manager_id=manager.user_id,
                        error_message=str(e),
                    )
                    responses.append(error_response)
                    logger.error(
                        f"Failed to send notification to manager {manager.user_id}: {e}"
                    )

            return responses

        except (ManagerNotFoundError, TemplateError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending transaction notification: {e}")
            raise NotificationError(
                f"Failed to send notification: {e}",
                transaction_id=notification_data.transaction_id,
            )

    async def send_rate_request_notification(
        self, notification_data: NotificationData
    ) -> List[NotificationResponse]:
        """Send rate request notification to managers.

        Args:
            notification_data: Rate request notification data

        Returns:
            List of notification responses
        """
        return await self.send_transaction_notification(
            notification_data, template_name="rate_request"
        )

    async def send_error_notification(
        self,
        transaction_id: str,
        user_id: int,
        error_message: str,
        username: str | None = None,
        full_name: str | None = None,
    ) -> List[NotificationResponse]:
        """Send error notification to all active managers.

        Args:
            transaction_id: Transaction identifier
            user_id: User ID who encountered error
            error_message: Error description
            username: User's username
            full_name: User's full name

        Returns:
            List of notification responses
        """
        try:
            # Create dummy calculation result for error notification
            from services.calculation_service import CalculationResult
            from decimal import Decimal

            dummy_result = CalculationResult(
                base_currency="ERROR",
                quote_currency="ERROR",
                input_amount=Decimal("0"),
                market_rate=Decimal("0"),
                markup_rate=Decimal("0"),
                final_rate=Decimal("0"),
                output_amount=Decimal("0"),
                markup_amount=Decimal("0"),
                spread_percentage=Decimal("0"),
                calculation_direction="error",
                formatted_input="Error",
                formatted_output="Error",
                formatted_rate="Error",
            )

            notification_data = NotificationData(
                transaction_id=transaction_id,
                user_id=user_id,
                username=username,
                full_name=full_name,
                calculation_result=dummy_result,
                additional_info={"error_message": error_message},
            )

            # Send to all active managers
            managers = self._get_all_active_managers()
            if not managers:
                logger.warning("No active managers found for error notification")
                return []

            responses = []
            for manager in managers:
                try:
                    template = self._templates["error"]
                    # Add error message to template variables
                    template.body_template = template.body_template.replace(
                        "{error_message}", error_message
                    )

                    response = await self._send_notification_to_manager(
                        manager, notification_data, template
                    )
                    responses.append(response)
                    logger.info(f"Error notification sent to manager {manager.user_id}")
                except Exception as e:
                    error_response = NotificationResponse(
                        success=False,
                        manager_id=manager.user_id,
                        error_message=str(e),
                    )
                    responses.append(error_response)
                    logger.error(
                        f"Failed to send error notification to manager {manager.user_id}: {e}"
                    )

            return responses

        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            raise NotificationError(f"Error notification failed: {e}")

    async def _send_notification_to_manager(
        self,
        manager: ManagerConfig,
        notification_data: NotificationData,
        template: NotificationTemplate,
    ) -> NotificationResponse:
        """Send notification to a specific manager.

        Args:
            manager: Manager configuration
            notification_data: Notification data
            template: Message template

        Returns:
            Notification response

        Raises:
            TelegramDeliveryError: If message delivery fails
        """
        try:
            # Format message using template
            message_text = template.format_message(notification_data)

            # Create keyboard if needed
            reply_markup = None
            if template.include_action_buttons:
                reply_markup = self._create_action_buttons(
                    notification_data.transaction_id, notification_data.currency_pair
                )

            # Send message
            message = await self.bot.send_message(
                chat_id=manager.user_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )

            return NotificationResponse(
                success=True,
                message_id=message.message_id,
                manager_id=manager.user_id,
            )

        except TelegramForbiddenError as e:
            error_msg = f"Manager {manager.user_id} blocked the bot"
            logger.warning(error_msg)
            raise TelegramDeliveryError(error_msg, manager_id=manager.user_id) from e

        except TelegramBadRequest as e:
            error_msg = f"Invalid request to manager {manager.user_id}: {e}"
            logger.error(error_msg)
            raise TelegramDeliveryError(error_msg, manager_id=manager.user_id) from e

        except TelegramAPIError as e:
            error_msg = f"Telegram API error for manager {manager.user_id}: {e}"
            logger.error(error_msg)
            raise TelegramDeliveryError(error_msg, manager_id=manager.user_id) from e

        except Exception as e:
            error_msg = f"Unexpected error sending to manager {manager.user_id}: {e}"
            logger.error(error_msg)
            raise TelegramDeliveryError(error_msg, manager_id=manager.user_id) from e

    async def handle_manager_callback(
        self, callback_data: str, manager_id: int, message_id: int
    ) -> bool:
        """Handle callback from manager action buttons.

        Args:
            callback_data: Callback data from button
            manager_id: Manager user ID
            message_id: Message ID with buttons

        Returns:
            True if callback handled successfully

        Raises:
            NotificationError: If callback handling fails
        """
        try:
            # Parse callback data
            parts = callback_data.split(":", 1)
            if len(parts) != 2:
                raise NotificationError(
                    f"Invalid callback data format: {callback_data}"
                )

            action, transaction_id = parts

            # Log manager action
            logger.info(
                f"Manager {manager_id} performed action '{action}' on transaction {transaction_id}"
            )

            # Update message to show action taken
            action_messages = {
                "confirm": "✅ <b>Заявка подтверждена</b>",
                "reject": "❌ <b>Заявка отклонена</b>",
                "processing": "⏳ <b>Заявка в обработке</b>",
                "contact": "💬 <b>Связь с клиентом установлена</b>",
                "details": "📊 <b>Детали просмотрены</b>",
            }

            status_message = action_messages.get(
                action, f"ℹ️ <b>Действие: {action}</b>"
            )

            # Update message with status
            await self.bot.edit_message_reply_markup(
                chat_id=manager_id,
                message_id=message_id,
                reply_markup=None,  # Remove buttons
            )

            # Send status update
            await self.bot.send_message(
                chat_id=manager_id,
                text=f"{status_message}\n\n📋 ID транзакции: <code>{transaction_id}</code>\n⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML",
            )

            return True

        except TelegramAPIError as e:
            logger.error(f"Telegram error handling callback: {e}")
            raise NotificationError(f"Failed to handle callback: {e}")
        except Exception as e:
            logger.error(f"Error handling manager callback: {e}")
            raise NotificationError(f"Callback handling failed: {e}")

    def add_custom_template(self, name: str, template: NotificationTemplate) -> None:
        """Add custom notification template.

        Args:
            name: Template name
            template: Template configuration
        """
        self._templates[name] = template
        logger.info(f"Added custom template: {name}")

    def get_template(self, name: str) -> NotificationTemplate | None:
        """Get notification template by name.

        Args:
            name: Template name

        Returns:
            Template configuration or None if not found
        """
        return self._templates.get(name)

    def list_templates(self) -> List[str]:
        """Get list of available template names.

        Returns:
            List of template names
        """
        return list(self._templates.keys())

    async def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification service statistics.

        Returns:
            Dictionary with service statistics
        """
        active_managers = self._get_all_active_managers()
        managers_with_pairs = sum(
            1 for manager in active_managers if manager.currency_pairs
        )

        return {
            "total_templates": len(self._templates),
            "active_managers": len(active_managers),
            "managers_with_pairs": managers_with_pairs,
            "default_manager_configured": self.settings.default_manager_id is not None,
            "notification_enabled_managers": sum(
                1 for manager in active_managers if manager.notification_enabled
            ),
        }

    def validate_manager_access(self, manager_id: int, currency_pair: str) -> bool:
        """Validate if manager has access to currency pair.

        Args:
            manager_id: Manager user ID
            currency_pair: Currency pair string

        Returns:
            True if manager has access
        """
        manager = self.settings.managers.get(manager_id)
        if not manager or not manager.is_active:
            return False

        # Check if manager is assigned to this pair
        if currency_pair in manager.currency_pairs:
            return True

        # Check if manager is default manager
        if manager_id == self.settings.default_manager_id:
            return True

        return False

    async def broadcast_message(
        self, message: str, parse_mode: str = "HTML"
    ) -> List[NotificationResponse]:
        """Broadcast message to all active managers.

        Args:
            message: Message text to broadcast
            parse_mode: Message parse mode

        Returns:
            List of notification responses
        """
        managers = self._get_all_active_managers()
        responses = []

        for manager in managers:
            try:
                sent_message = await self.bot.send_message(
                    chat_id=manager.user_id,
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )

                response = NotificationResponse(
                    success=True,
                    message_id=sent_message.message_id,
                    manager_id=manager.user_id,
                )
                responses.append(response)
                logger.info(f"Broadcast message sent to manager {manager.user_id}")

            except Exception as e:
                error_response = NotificationResponse(
                    success=False,
                    manager_id=manager.user_id,
                    error_message=str(e),
                )
                responses.append(error_response)
                logger.error(f"Failed to broadcast to manager {manager.user_id}: {e}")

        return responses
