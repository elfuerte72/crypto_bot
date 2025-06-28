"""Notification templates for the crypto bot.

This module provides message templates for various notification types including
rate alerts, calculation results, admin notifications, and error messages.
"""

from __future__ import annotations

from typing import Any, Dict

from services.notification_service import NotificationTemplate


class NotificationTemplates:
    """Collection of predefined notification templates."""

    @staticmethod
    def get_default_templates() -> Dict[str, NotificationTemplate]:
        """Get default notification templates.

        Returns:
            Dictionary of template name to NotificationTemplate mappings
        """
        return {
            "transaction": NotificationTemplate(
                title="💱 Новая транзакция",
                body_template="""🔔 <b>Новая заявка на обмен валют</b>

📋 <b>Детали транзакции:</b>
• ID: <code>{transaction_id}</code>
• Время: {timestamp}

👤 <b>Клиент:</b>
• Имя: {user_display_name}
• ID: <code>{user_id}</code>
{username_line}

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
            ),
            "rate_request": NotificationTemplate(
                title="📊 Запрос курса",
                body_template="""📊 <b>Запрос курса валют</b>

👤 <b>Клиент:</b>
• Имя: {user_display_name}
• ID: <code>{user_id}</code>
{username_line}

💱 <b>Запрос:</b>
• Валютная пара: <b>{currency_pair}</b>
• Время: {timestamp}

💰 <b>Текущий курс:</b>
• {exchange_rate}
• Наценка: {markup_rate}

ℹ️ Клиент запросил актуальный курс обмена.""",
                include_user_info=True,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
            "calculation_request": NotificationTemplate(
                title="🧮 Расчет суммы",
                body_template="""🧮 <b>Запрос расчета обмена</b>

👤 <b>Клиент:</b>
• Имя: {user_display_name}
• ID: <code>{user_id}</code>
{username_line}

💰 <b>Расчет:</b>
• Валютная пара: <b>{currency_pair}</b>
• Направление: {direction}
• Отдает: <b>{input_amount}</b>
• Получает: <b>{output_amount}</b>
• Курс: {exchange_rate}
• Время: {timestamp}

📊 <b>Детали:</b>
• Наценка: {markup_rate}
• Наша прибыль: <b>{markup_amount} {quote_currency}</b>

💡 Клиент рассчитал сумму обмена.""",
                include_user_info=True,
                include_calculation_details=True,
                include_action_buttons=False,
            ),
            "error": NotificationTemplate(
                title="⚠️ Ошибка системы",
                body_template="""⚠️ <b>Системная ошибка</b>

📋 <b>Детали:</b>
• ID транзакции: <code>{transaction_id}</code>
• Время: {timestamp}
• Ошибка: {error_message}

👤 <b>Пользователь:</b>
• {user_display_name} (ID: <code>{user_id}</code>)
{username_line}

🔧 <b>Требуется вмешательство администратора.</b>

⚡ Пожалуйста, проверьте систему и свяжитесь с клиентом при необходимости.""",
                include_user_info=True,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
            "system_alert": NotificationTemplate(
                title="🚨 Системное уведомление",
                body_template="""🚨 <b>Системное уведомление</b>

📋 <b>Информация:</b>
• Время: {timestamp}
• Тип: {alert_type}
• Сообщение: {alert_message}

🔍 <b>Детали:</b>
{alert_details}

⚠️ Требуется внимание администратора.""",
                include_user_info=False,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
            "high_volume_alert": NotificationTemplate(
                title="📈 Уведомление о крупной сумме",
                body_template="""📈 <b>Крупная транзакция</b>

⚠️ <b>Внимание! Сумма превышает лимит</b>

📋 <b>Детали транзакции:</b>
• ID: <code>{transaction_id}</code>
• Время: {timestamp}

👤 <b>Клиент:</b>
• Имя: {user_display_name}
• ID: <code>{user_id}</code>
{username_line}

💰 <b>Обмен:</b>
• Валютная пара: <b>{currency_pair}</b>
• Сумма: <b>{input_amount}</b> ➡️ <b>{output_amount}</b>
• Курс: {exchange_rate}

📊 <b>Прибыль:</b>
• Наценка: {markup_rate}
• Наша прибыль: <b>{markup_amount} {quote_currency}</b>

⚡ <b>Требуется особое внимание и проверка!</b>""",
                include_user_info=True,
                include_calculation_details=True,
                include_action_buttons=True,
            ),
            "daily_summary": NotificationTemplate(
                title="📊 Ежедневная сводка",
                body_template="""📊 <b>Ежедневная сводка</b>

📅 <b>Дата:</b> {date}

📈 <b>Статистика:</b>
• Всего транзакций: {total_transactions}
• Успешных: {successful_transactions}
• Отклоненных: {rejected_transactions}
• В обработке: {pending_transactions}

💰 <b>Финансы:</b>
• Общий оборот: <b>{total_volume}</b>
• Прибыль: <b>{total_profit}</b>
• Средний чек: <b>{average_transaction}</b>

🔝 <b>Топ валютные пары:</b>
{top_pairs}

📊 <b>Активность менеджеров:</b>
{manager_activity}""",
                include_user_info=False,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
            "manager_assignment": NotificationTemplate(
                title="👨‍💼 Назначение менеджера",
                body_template="""👨‍💼 <b>Назначение менеджера</b>

🎯 <b>Вы назначены менеджером</b>

📋 <b>Детали:</b>
• Валютные пары: <b>{currency_pairs}</b>
• Время назначения: {timestamp}
• Назначил: {assigned_by}

📢 <b>Ваши обязанности:</b>
• Обработка заявок на обмен валют
• Своевременное реагирование на уведомления
• Поддержка клиентов по назначенным парам

✅ <b>Вы будете получать уведомления о новых транзакциях!</b>""",
                include_user_info=False,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
            "markup_change": NotificationTemplate(
                title="📊 Изменение наценки",
                body_template="""📊 <b>Изменение наценки</b>

💱 <b>Обновлена наценка для валютной пары</b>

📋 <b>Детали:</b>
• Валютная пара: <b>{currency_pair}</b>
• Старая наценка: {old_markup_rate}%
• Новая наценка: <b>{new_markup_rate}%</b>
• Время изменения: {timestamp}
• Изменил: {changed_by}

📈 <b>Влияние на прибыль:</b>
• Изменение: {markup_change}%
• Новая прибыль с суммы 1000 USD: <b>{profit_example}</b>

ℹ️ Новая наценка вступила в силу немедленно.""",
                include_user_info=False,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
            "api_error": NotificationTemplate(
                title="🔌 Ошибка API",
                body_template="""🔌 <b>Ошибка внешнего API</b>

⚠️ <b>Проблема с получением курсов валют</b>

📋 <b>Детали:</b>
• API: Rapira Exchange
• Время ошибки: {timestamp}
• Код ошибки: {error_code}
• Сообщение: {error_message}

🔄 <b>Статус:</b>
• Попыток переподключения: {retry_count}
• Последняя успешная синхронизация: {last_success}

⚡ <b>Действия:</b>
• Система пытается восстановить соединение
• Используются кешированные курсы
• Уведомите техподдержку при длительной недоступности""",
                include_user_info=False,
                include_calculation_details=False,
                include_action_buttons=False,
            ),
        }

    @staticmethod
    def get_template_by_name(name: str) -> NotificationTemplate | None:
        """Get template by name.

        Args:
            name: Template name

        Returns:
            NotificationTemplate or None if not found
        """
        templates = NotificationTemplates.get_default_templates()
        return templates.get(name)

    @staticmethod
    def get_available_template_names() -> list[str]:
        """Get list of available template names.

        Returns:
            List of template names
        """
        return list(NotificationTemplates.get_default_templates().keys())

    @staticmethod
    def create_custom_template(
        title: str,
        body_template: str,
        include_user_info: bool = True,
        include_calculation_details: bool = True,
        include_action_buttons: bool = False,
    ) -> NotificationTemplate:
        """Create custom notification template.

        Args:
            title: Template title
            body_template: Message body template with placeholders
            include_user_info: Whether to include user information
            include_calculation_details: Whether to include calculation details
            include_action_buttons: Whether to include action buttons

        Returns:
            NotificationTemplate instance
        """
        return NotificationTemplate(
            title=title,
            body_template=body_template,
            include_user_info=include_user_info,
            include_calculation_details=include_calculation_details,
            include_action_buttons=include_action_buttons,
        )

    @staticmethod
    def get_template_variables() -> Dict[str, str]:
        """Get available template variables and their descriptions.

        Returns:
            Dictionary of variable names to descriptions
        """
        return {
            # Transaction variables
            "transaction_id": "Unique transaction identifier",
            "timestamp": "Formatted timestamp of the transaction",
            "currency_pair": "Currency pair (e.g., USD/RUB)",
            "direction": "Transaction direction (Buy/Sell)",
            # User variables
            "user_id": "Telegram user ID",
            "user_display_name": "User's display name (full name, username, or ID)",
            "username": "User's Telegram username",
            "full_name": "User's full name",
            "username_line": "Formatted username line (if available)",
            # Calculation variables
            "input_amount": "Formatted input amount with currency",
            "output_amount": "Formatted output amount with currency",
            "exchange_rate": "Formatted exchange rate",
            "markup_rate": "Markup rate percentage",
            "markup_amount": "Markup amount in quote currency",
            "base_currency": "Base currency code",
            "quote_currency": "Quote currency code",
            # Error variables
            "error_message": "Error description",
            "error_code": "Error code (if applicable)",
            # System variables
            "alert_type": "Type of system alert",
            "alert_message": "Alert message",
            "alert_details": "Detailed alert information",
            # Statistics variables
            "date": "Date for reports",
            "total_transactions": "Total number of transactions",
            "successful_transactions": "Number of successful transactions",
            "rejected_transactions": "Number of rejected transactions",
            "pending_transactions": "Number of pending transactions",
            "total_volume": "Total transaction volume",
            "total_profit": "Total profit",
            "average_transaction": "Average transaction amount",
            "top_pairs": "Top currency pairs by volume",
            "manager_activity": "Manager activity statistics",
            # Management variables
            "currency_pairs": "List of currency pairs",
            "assigned_by": "Who assigned the manager",
            "old_markup_rate": "Previous markup rate",
            "new_markup_rate": "New markup rate",
            "markup_change": "Markup change percentage",
            "profit_example": "Example profit calculation",
            "changed_by": "Who changed the markup",
            # API variables
            "retry_count": "Number of retry attempts",
            "last_success": "Last successful API call timestamp",
        }

    @staticmethod
    def validate_template(template: NotificationTemplate) -> list[str]:
        """Validate template for common issues.

        Args:
            template: Template to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check if template has required fields
        if not template.title:
            errors.append("Template title is required")

        if not template.body_template:
            errors.append("Template body is required")

        # Check for common template variable issues
        body = template.body_template

        # Check for unmatched braces
        open_braces = body.count("{")
        close_braces = body.count("}")
        if open_braces != close_braces:
            errors.append("Unmatched braces in template body")

        # Check for HTML tag issues
        if "<b>" in body and "</b>" not in body:
            errors.append("Unclosed <b> tag in template")

        if "<code>" in body and "</code>" not in body:
            errors.append("Unclosed <code> tag in template")

        # Check for required variables based on template settings
        if template.include_user_info:
            required_vars = ["user_display_name", "user_id"]
            for var in required_vars:
                if f"{{{var}}}" not in body:
                    errors.append(f"Missing required user variable: {var}")

        if template.include_calculation_details:
            required_vars = ["currency_pair", "input_amount", "output_amount"]
            for var in required_vars:
                if f"{{{var}}}" not in body:
                    errors.append(f"Missing required calculation variable: {var}")

        return errors
