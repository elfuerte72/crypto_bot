"""Tests for notification service functionality.

This module contains comprehensive tests for the NotificationService class,
covering all notification scenarios, template handling, and error conditions.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramAPIError,
)
from aiogram.types import Message, InlineKeyboardMarkup

from src.config.models import Settings, ManagerConfig, CurrencyPair
from src.services.notification_service import (
    NotificationService,
    NotificationData,
    NotificationTemplate,
    NotificationResponse,
    NotificationError,
    ManagerNotFoundError,
    TemplateError,
    TelegramDeliveryError,
)
from src.services.calculation_service import CalculationResult
from src.templates.notification_templates import NotificationTemplates


class TestNotificationData:
    """Test NotificationData model."""

    def test_notification_data_creation(self):
        """Test NotificationData creation with valid data."""
        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            username="testuser",
            full_name="Test User",
            calculation_result=calc_result,
        )

        assert data.transaction_id == "TXN123456789"
        assert data.user_id == 12345
        assert data.username == "testuser"
        assert data.full_name == "Test User"
        assert data.calculation_result == calc_result
        assert isinstance(data.timestamp, datetime)

    def test_notification_data_validation(self):
        """Test NotificationData validation."""
        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        # Test invalid transaction ID
        with pytest.raises(
            ValueError, match="Transaction ID must be at least 8 characters"
        ):
            NotificationData(
                transaction_id="SHORT",
                user_id=12345,
                calculation_result=calc_result,
            )

    def test_user_display_name_property(self):
        """Test user_display_name property logic."""
        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        # Test with full name
        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            full_name="John Doe",
            calculation_result=calc_result,
        )
        assert data.user_display_name == "John Doe"

        # Test with username only
        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            username="johndoe",
            calculation_result=calc_result,
        )
        assert data.user_display_name == "@johndoe"

        # Test with user ID only
        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            calculation_result=calc_result,
        )
        assert data.user_display_name == "User 12345"

    def test_currency_pair_property(self):
        """Test currency_pair property."""
        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            calculation_result=calc_result,
        )

        assert data.currency_pair == "USD/RUB"

    def test_formatted_timestamp_property(self):
        """Test formatted_timestamp property."""
        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        test_time = datetime(2024, 1, 15, 10, 30, 45)
        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            calculation_result=calc_result,
            timestamp=test_time,
        )

        assert data.formatted_timestamp == "15.01.2024 10:30:45 UTC"


class TestNotificationTemplate:
    """Test NotificationTemplate model."""

    def test_template_creation(self):
        """Test NotificationTemplate creation."""
        template = NotificationTemplate(
            title="Test Title",
            body_template="Hello {user_display_name}!",
            include_user_info=True,
            include_calculation_details=False,
            include_action_buttons=False,
        )

        assert template.title == "Test Title"
        assert template.body_template == "Hello {user_display_name}!"
        assert template.include_user_info is True
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

    def test_format_message(self):
        """Test message formatting with template."""
        template = NotificationTemplate(
            title="Test",
            body_template="Hello {user_display_name}! Transaction: {transaction_id}",
        )

        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            full_name="John Doe",
            calculation_result=calc_result,
        )

        formatted = template.format_message(data)
        assert "Hello John Doe!" in formatted
        assert "Transaction: TXN123456789" in formatted

    def test_format_message_with_missing_variable(self):
        """Test message formatting with missing template variable."""
        template = NotificationTemplate(
            title="Test",
            body_template="Hello {missing_variable}!",
        )

        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        data = NotificationData(
            transaction_id="TXN123456789",
            user_id=12345,
            calculation_result=calc_result,
        )

        formatted = template.format_message(data)
        assert "Template error:" in formatted


class TestNotificationResponse:
    """Test NotificationResponse model."""

    def test_notification_response_creation(self):
        """Test NotificationResponse creation."""
        response = NotificationResponse(
            success=True,
            message_id=12345,
            manager_id=67890,
        )

        assert response.success is True
        assert response.message_id == 12345
        assert response.manager_id == 67890
        assert response.error_message is None
        assert isinstance(response.sent_at, datetime)

    def test_is_success_property(self):
        """Test is_success property."""
        # Successful response
        response = NotificationResponse(
            success=True,
            message_id=12345,
            manager_id=67890,
        )
        assert response.is_success is True

        # Failed response (no message_id)
        response = NotificationResponse(
            success=True,
            manager_id=67890,
        )
        assert response.is_success is False

        # Failed response (success=False)
        response = NotificationResponse(
            success=False,
            message_id=12345,
            manager_id=67890,
        )
        assert response.is_success is False


class TestNotificationService:
    """Test NotificationService functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock bot."""
        bot = AsyncMock(spec=Bot)
        return bot

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()

        # Add test managers
        settings.managers[12345] = ManagerConfig(
            user_id=12345,
            name="Test Manager 1",
            currency_pairs={"USD/RUB", "EUR/USD"},
            is_active=True,
            notification_enabled=True,
        )

        settings.managers[67890] = ManagerConfig(
            user_id=67890,
            name="Test Manager 2",
            currency_pairs={"BTC/USD"},
            is_active=True,
            notification_enabled=True,
        )

        settings.managers[99999] = ManagerConfig(
            user_id=99999,
            name="Inactive Manager",
            currency_pairs={"ETH/USD"},
            is_active=False,
            notification_enabled=True,
        )

        # Set default manager
        settings.default_manager_id = 12345

        # Add currency pairs
        settings.currency_pairs["USD/RUB"] = CurrencyPair(
            base="USD",
            quote="RUB",
            markup_rate=2.5,
        )

        return settings

    @pytest.fixture
    def notification_service(self, settings, mock_bot):
        """Create notification service."""
        return NotificationService(settings, mock_bot)

    @pytest.fixture
    def sample_notification_data(self):
        """Create sample notification data."""
        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        return NotificationData(
            transaction_id="TXN123456789",
            user_id=11111,
            username="testuser",
            full_name="Test User",
            calculation_result=calc_result,
        )

    def test_service_initialization(self, notification_service):
        """Test service initialization."""
        assert notification_service.bot is not None
        assert len(notification_service._templates) > 0
        assert "transaction" in notification_service._templates
        assert "rate_request" in notification_service._templates
        assert "error" in notification_service._templates

    def test_get_manager_for_pair(self, notification_service):
        """Test getting manager for currency pair."""
        # Test existing pair
        manager = notification_service._get_manager_for_pair("USD/RUB")
        assert manager is not None
        assert manager.user_id == 12345

        # Test non-existing pair - should return default manager
        manager = notification_service._get_manager_for_pair("XYZ/ABC")
        assert manager is not None  # Returns default manager
        assert manager.user_id == 12345

    def test_get_default_manager(self, notification_service):
        """Test getting default manager."""
        manager = notification_service._get_default_manager()
        assert manager is not None
        assert manager.user_id == 12345

    def test_get_all_active_managers(self, notification_service):
        """Test getting all active managers."""
        managers = notification_service._get_all_active_managers()
        assert len(managers) == 2  # Two active managers
        manager_ids = [m.user_id for m in managers]
        assert 12345 in manager_ids
        assert 67890 in manager_ids
        assert 99999 not in manager_ids  # Inactive

    def test_create_action_buttons(self, notification_service):
        """Test creating action buttons."""
        buttons = notification_service._create_action_buttons("TXN123", "USD/RUB")

        assert isinstance(buttons, InlineKeyboardMarkup)
        assert len(buttons.inline_keyboard) == 3  # 3 rows
        assert len(buttons.inline_keyboard[0]) == 2  # First row has 2 buttons
        assert len(buttons.inline_keyboard[1]) == 2  # Second row has 2 buttons
        assert len(buttons.inline_keyboard[2]) == 1  # Third row has 1 button

        # Check callback data
        first_button = buttons.inline_keyboard[0][0]
        assert first_button.callback_data == "confirm:TXN123"

    @pytest.mark.asyncio
    async def test_send_transaction_notification_success(
        self, notification_service, sample_notification_data, mock_bot
    ):
        """Test successful transaction notification sending."""
        # Mock successful message sending
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 12345
        mock_bot.send_message.return_value = mock_message

        responses = await notification_service.send_transaction_notification(
            sample_notification_data
        )

        assert len(responses) == 1
        assert responses[0].success is True
        assert responses[0].message_id == 12345
        assert responses[0].manager_id == 12345

        # Verify bot.send_message was called
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["chat_id"] == 12345
        assert "Новая заявка на обмен валют" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_send_transaction_notification_no_manager(
        self, notification_service, sample_notification_data, mock_bot
    ):
        """Test transaction notification with no manager found."""
        # Remove default manager to trigger error
        notification_service.settings.default_manager_id = None

        # Change currency pair to one without manager
        sample_notification_data.calculation_result.base_currency = "XYZ"
        sample_notification_data.calculation_result.quote_currency = "ABC"

        with pytest.raises(ManagerNotFoundError):
            await notification_service.send_transaction_notification(
                sample_notification_data
            )

    @pytest.mark.asyncio
    async def test_send_transaction_notification_telegram_error(
        self, notification_service, sample_notification_data, mock_bot
    ):
        """Test transaction notification with Telegram error."""
        # Mock Telegram forbidden error
        mock_bot.send_message.side_effect = TelegramForbiddenError(
            method="sendMessage", message="Bot was blocked"
        )

        responses = await notification_service.send_transaction_notification(
            sample_notification_data
        )

        assert len(responses) == 1
        assert responses[0].success is False
        assert "blocked the bot" in responses[0].error_message

    @pytest.mark.asyncio
    async def test_send_rate_request_notification(
        self, notification_service, sample_notification_data, mock_bot
    ):
        """Test rate request notification."""
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 12345
        mock_bot.send_message.return_value = mock_message

        responses = await notification_service.send_rate_request_notification(
            sample_notification_data
        )

        assert len(responses) == 1
        assert responses[0].success is True

        # Verify correct template was used
        call_args = mock_bot.send_message.call_args
        assert "Запрос курса валют" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_error_notification(self, notification_service, mock_bot):
        """Test error notification."""
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 12345
        mock_bot.send_message.return_value = mock_message

        responses = await notification_service.send_error_notification(
            transaction_id="TXN123456789",
            user_id=11111,
            error_message="Test error message",
            username="testuser",
            full_name="Test User",
        )

        assert len(responses) == 2  # Sent to all active managers
        assert all(r.success for r in responses)

        # Verify error message was included
        call_args = mock_bot.send_message.call_args
        assert "Системная ошибка" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_handle_manager_callback_success(
        self, notification_service, mock_bot
    ):
        """Test successful manager callback handling."""
        mock_bot.edit_message_reply_markup.return_value = True
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 67890
        mock_bot.send_message.return_value = mock_message

        result = await notification_service.handle_manager_callback(
            callback_data="confirm:TXN123456789",
            manager_id=12345,
            message_id=54321,
        )

        assert result is True
        mock_bot.edit_message_reply_markup.assert_called_once()
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_manager_callback_invalid_format(self, notification_service):
        """Test manager callback with invalid format."""
        with pytest.raises(NotificationError, match="Invalid callback data format"):
            await notification_service.handle_manager_callback(
                callback_data="invalid_format",
                manager_id=12345,
                message_id=54321,
            )

    @pytest.mark.asyncio
    async def test_handle_manager_callback_telegram_error(
        self, notification_service, mock_bot
    ):
        """Test manager callback with Telegram error."""
        mock_bot.edit_message_reply_markup.side_effect = TelegramAPIError(
            method="editMessageReplyMarkup", message="API Error"
        )

        with pytest.raises(NotificationError, match="Failed to handle callback"):
            await notification_service.handle_manager_callback(
                callback_data="confirm:TXN123456789",
                manager_id=12345,
                message_id=54321,
            )

    def test_add_custom_template(self, notification_service):
        """Test adding custom template."""
        custom_template = NotificationTemplate(
            title="Custom Template",
            body_template="Custom body: {transaction_id}",
        )

        notification_service.add_custom_template("custom", custom_template)

        retrieved = notification_service.get_template("custom")
        assert retrieved is not None
        assert retrieved.title == "Custom Template"

    def test_get_template(self, notification_service):
        """Test getting template by name."""
        template = notification_service.get_template("transaction")
        assert template is not None
        assert template.title == "💱 Новая транзакция"

        # Test non-existing template
        template = notification_service.get_template("non_existing")
        assert template is None

    def test_list_templates(self, notification_service):
        """Test listing all templates."""
        templates = notification_service.list_templates()
        assert "transaction" in templates
        assert "rate_request" in templates
        assert "error" in templates
        assert len(templates) >= 3

    @pytest.mark.asyncio
    async def test_get_notification_stats(self, notification_service):
        """Test getting notification statistics."""
        stats = await notification_service.get_notification_stats()

        assert "total_templates" in stats
        assert "active_managers" in stats
        assert "managers_with_pairs" in stats
        assert "default_manager_configured" in stats
        assert "notification_enabled_managers" in stats

        assert stats["active_managers"] == 2
        assert stats["default_manager_configured"] is True
        assert stats["notification_enabled_managers"] == 2

    def test_validate_manager_access(self, notification_service):
        """Test manager access validation."""
        # Test manager with specific pair access
        assert notification_service.validate_manager_access(12345, "USD/RUB") is True
        assert notification_service.validate_manager_access(12345, "EUR/USD") is True
        assert notification_service.validate_manager_access(67890, "BTC/USD") is True

        # Test manager without access
        assert notification_service.validate_manager_access(67890, "USD/RUB") is False

        # Test default manager access
        assert notification_service.validate_manager_access(12345, "XYZ/ABC") is True

        # Test inactive manager
        assert notification_service.validate_manager_access(99999, "ETH/USD") is False

        # Test non-existing manager
        assert notification_service.validate_manager_access(00000, "USD/RUB") is False

    @pytest.mark.asyncio
    async def test_broadcast_message_success(self, notification_service, mock_bot):
        """Test successful message broadcasting."""
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 12345
        mock_bot.send_message.return_value = mock_message

        responses = await notification_service.broadcast_message(
            "Test broadcast message"
        )

        assert len(responses) == 2  # Two active managers
        assert all(r.success for r in responses)

        # Verify bot.send_message was called for each manager
        assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_message_partial_failure(
        self, notification_service, mock_bot
    ):
        """Test message broadcasting with partial failures."""
        # First call succeeds, second fails
        mock_message = MagicMock(spec=Message)
        mock_message.message_id = 12345
        mock_bot.send_message.side_effect = [
            mock_message,
            TelegramForbiddenError(method="sendMessage", message="Blocked"),
        ]

        responses = await notification_service.broadcast_message(
            "Test broadcast message"
        )

        assert len(responses) == 2
        assert responses[0].success is True
        assert responses[1].success is False
        assert "Blocked" in responses[1].error_message

    @pytest.mark.asyncio
    async def test_send_notification_to_manager_forbidden(
        self, notification_service, mock_bot
    ):
        """Test sending notification when bot is blocked by manager."""
        mock_bot.send_message.side_effect = TelegramForbiddenError(
            method="sendMessage", message="Forbidden: bot was blocked by the user"
        )

        manager = ManagerConfig(
            user_id=12345,
            name="Test Manager",
            currency_pairs=set(),
            is_active=True,
            notification_enabled=True,
        )

        template = NotificationTemplate(
            title="Test",
            body_template="Test message",
        )

        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        notification_data = NotificationData(
            transaction_id="TXN123456789",
            user_id=11111,
            calculation_result=calc_result,
        )

        with pytest.raises(TelegramDeliveryError, match="blocked the bot"):
            await notification_service._send_notification_to_manager(
                manager, notification_data, template
            )

    @pytest.mark.asyncio
    async def test_send_notification_to_manager_bad_request(
        self, notification_service, mock_bot
    ):
        """Test sending notification with bad request error."""
        mock_bot.send_message.side_effect = TelegramBadRequest(
            method="sendMessage", message="Bad Request: invalid chat_id"
        )

        manager = ManagerConfig(
            user_id=12345,
            name="Test Manager",
            currency_pairs=set(),
            is_active=True,
            notification_enabled=True,
        )

        template = NotificationTemplate(
            title="Test",
            body_template="Test message",
        )

        calc_result = CalculationResult(
            base_currency="USD",
            quote_currency="RUB",
            input_amount=Decimal("100"),
            market_rate=Decimal("75.5"),
            markup_rate=Decimal("2.5"),
            final_rate=Decimal("77.39"),
            output_amount=Decimal("7739"),
            markup_amount=Decimal("189"),
            spread_percentage=Decimal("0.1"),
            calculation_direction="buy",
            formatted_input="$100.00",
            formatted_output="7,739.00 ₽",
            formatted_rate="1 USD = 77.39 ₽",
        )

        notification_data = NotificationData(
            transaction_id="TXN123456789",
            user_id=11111,
            calculation_result=calc_result,
        )

        with pytest.raises(TelegramDeliveryError, match="Invalid request"):
            await notification_service._send_notification_to_manager(
                manager, notification_data, template
            )

    def test_template_error_handling(self, notification_service):
        """Test template error handling."""
        with pytest.raises(TemplateError, match="Template 'non_existing' not found"):
            # This would be called in send_transaction_notification
            template = notification_service._templates.get("non_existing")
            if not template:
                raise TemplateError("Template 'non_existing' not found")


class TestNotificationTemplates:
    """Test NotificationTemplates utility class."""

    def test_get_default_templates(self):
        """Test getting default templates."""
        templates = NotificationTemplates.get_default_templates()

        assert isinstance(templates, dict)
        assert len(templates) > 0
        assert "transaction" in templates
        assert "rate_request" in templates
        assert "error" in templates

    def test_get_template_by_name(self):
        """Test getting template by name."""
        template = NotificationTemplates.get_template_by_name("transaction")
        assert template is not None
        assert template.title == "💱 Новая транзакция"

        # Test non-existing template
        template = NotificationTemplates.get_template_by_name("non_existing")
        assert template is None

    def test_get_available_template_names(self):
        """Test getting available template names."""
        names = NotificationTemplates.get_available_template_names()
        assert isinstance(names, list)
        assert "transaction" in names
        assert "rate_request" in names
        assert "error" in names

    def test_create_custom_template(self):
        """Test creating custom template."""
        template = NotificationTemplates.create_custom_template(
            title="Custom Title",
            body_template="Custom body: {transaction_id}",
            include_user_info=False,
            include_calculation_details=True,
            include_action_buttons=True,
        )

        assert template.title == "Custom Title"
        assert template.body_template == "Custom body: {transaction_id}"
        assert template.include_user_info is False
        assert template.include_calculation_details is True
        assert template.include_action_buttons is True

    def test_get_template_variables(self):
        """Test getting template variables."""
        variables = NotificationTemplates.get_template_variables()

        assert isinstance(variables, dict)
        assert "transaction_id" in variables
        assert "user_display_name" in variables
        assert "currency_pair" in variables
        assert "input_amount" in variables
        assert "output_amount" in variables

    def test_validate_template_success(self):
        """Test successful template validation."""
        template = NotificationTemplate(
            title="Valid Template",
            body_template="Hello {user_display_name}! ID: {user_id}, Pair: {currency_pair}, In: {input_amount}, Out: {output_amount}",
            include_user_info=True,
            include_calculation_details=True,
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) == 0

    def test_validate_template_errors(self):
        """Test template validation with errors."""
        # Empty title
        template = NotificationTemplate(
            title="",
            body_template="Test body",
        )
        errors = NotificationTemplates.validate_template(template)
        assert "Template title is required" in errors

        # Empty body
        template = NotificationTemplate(
            title="Test Title",
            body_template="",
        )
        errors = NotificationTemplates.validate_template(template)
        assert "Template body is required" in errors

        # Unmatched braces
        template = NotificationTemplate(
            title="Test Title",
            body_template="Hello {user_name",
        )
        errors = NotificationTemplates.validate_template(template)
        assert "Unmatched braces in template body" in errors

        # Unclosed HTML tags
        template = NotificationTemplate(
            title="Test Title",
            body_template="<b>Bold text without closing tag",
        )
        errors = NotificationTemplates.validate_template(template)
        assert "Unclosed <b> tag in template" in errors

        # Missing required user variables
        template = NotificationTemplate(
            title="Test Title",
            body_template="Missing user info",
            include_user_info=True,
        )
        errors = NotificationTemplates.validate_template(template)
        assert any("Missing required user variable" in error for error in errors)

        # Missing required calculation variables
        template = NotificationTemplate(
            title="Test Title",
            body_template="Missing calculation info",
            include_calculation_details=True,
        )
        errors = NotificationTemplates.validate_template(template)
        assert any("Missing required calculation variable" in error for error in errors)


class TestNotificationExceptions:
    """Test notification exception classes."""

    def test_notification_error(self):
        """Test NotificationError exception."""
        error = NotificationError(
            message="Test error",
            manager_id=12345,
            transaction_id="TXN123",
        )

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.manager_id == 12345
        assert error.transaction_id == "TXN123"

    def test_manager_not_found_error(self):
        """Test ManagerNotFoundError exception."""
        error = ManagerNotFoundError(
            message="Manager not found",
            transaction_id="TXN123",
        )

        assert str(error) == "Manager not found"
        assert error.transaction_id == "TXN123"

    def test_template_error(self):
        """Test TemplateError exception."""
        error = TemplateError(
            message="Template error",
            transaction_id="TXN123",
        )

        assert str(error) == "Template error"
        assert error.transaction_id == "TXN123"

    def test_telegram_delivery_error(self):
        """Test TelegramDeliveryError exception."""
        error = TelegramDeliveryError(
            message="Delivery failed",
            manager_id=12345,
        )

        assert str(error) == "Delivery failed"
        assert error.manager_id == 12345
