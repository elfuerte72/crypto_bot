"""Unit tests for admin handlers module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.fsm.context import FSMContext

from bot.handlers.admin_handlers import (
    AdminService,
    AdminStates,
    get_admin_service,
    check_admin_access,
    cmd_set_markup,
    handle_markup_selection,
    handle_markup_value_input,
    handle_back_to_markup_selection,
)
from config.models import Settings, TelegramConfig, CurrencyPair


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Settings()
    settings.telegram = TelegramConfig(admin_user_ids=[123456789])
    settings.default_markup_rate = 2.5

    # Add some test currency pairs
    settings.currency_pairs = {
        "RUB/ZAR": CurrencyPair(base="RUB", quote="ZAR", markup_rate=3.0),
        "USDT/THB": CurrencyPair(base="USDT", quote="THB", markup_rate=2.0),
    }

    return settings


@pytest.fixture
def admin_service(mock_settings):
    """Create AdminService instance."""
    return AdminService(mock_settings)


@pytest.fixture
def mock_admin_user():
    """Create mock admin user."""
    return User(id=123456789, is_bot=False, first_name="Admin", username="admin_user")


@pytest.fixture
def mock_regular_user():
    """Create mock regular user."""
    return User(
        id=987654321, is_bot=False, first_name="Regular", username="regular_user"
    )


@pytest.fixture
def mock_chat():
    """Create mock chat."""
    return Chat(id=-100123456789, type="private")


@pytest.fixture
def mock_message(mock_admin_user, mock_chat):
    """Create mock message from admin user."""
    message = MagicMock(spec=Message)
    message.from_user = mock_admin_user
    message.chat = mock_chat
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_admin_user):
    """Create mock callback query from admin user."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = mock_admin_user
    callback.data = "markup:RUB:ZAR"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    return callback


@pytest.fixture
def mock_fsm_context():
    """Create mock FSM context."""
    context = MagicMock(spec=FSMContext)
    context.get_data = AsyncMock(return_value={})
    context.update_data = AsyncMock()
    context.set_state = AsyncMock()
    context.clear = AsyncMock()
    return context


class TestAdminService:
    """Test AdminService functionality."""

    def test_init(self, mock_settings):
        """Test AdminService initialization."""
        service = AdminService(mock_settings)
        assert service.settings == mock_settings

    def test_is_admin_true(self, admin_service):
        """Test is_admin returns True for admin user."""
        assert admin_service.is_admin(123456789) is True

    def test_is_admin_false(self, admin_service):
        """Test is_admin returns False for non-admin user."""
        assert admin_service.is_admin(987654321) is False

    def test_get_current_markup_existing_pair(self, admin_service):
        """Test getting markup for existing currency pair."""
        markup = admin_service.get_current_markup("RUB/ZAR")
        assert markup == 3.0

    def test_get_current_markup_non_existing_pair(self, admin_service):
        """Test getting markup for non-existing currency pair."""
        markup = admin_service.get_current_markup("EUR/USD")
        assert markup == 2.5  # Default markup rate

    def test_update_markup_rate_existing_pair(self, admin_service):
        """Test updating markup rate for existing pair."""
        result = admin_service.update_markup_rate("RUB/ZAR", 5.0)
        assert result is True
        assert admin_service.settings.currency_pairs["RUB/ZAR"].markup_rate == 5.0

    def test_update_markup_rate_new_pair(self, admin_service):
        """Test updating markup rate for new pair."""
        result = admin_service.update_markup_rate("EUR/USD", 4.0)
        assert result is True
        assert "EUR/USD" in admin_service.settings.currency_pairs
        assert admin_service.settings.currency_pairs["EUR/USD"].markup_rate == 4.0

    def test_update_markup_rate_invalid_range_low(self, admin_service):
        """Test updating markup rate with invalid low value."""
        result = admin_service.update_markup_rate("RUB/ZAR", -1.0)
        assert result is False

    def test_update_markup_rate_invalid_range_high(self, admin_service):
        """Test updating markup rate with invalid high value."""
        result = admin_service.update_markup_rate("RUB/ZAR", 101.0)
        assert result is False

    def test_update_markup_rate_invalid_pair_format(self, admin_service):
        """Test updating markup rate with invalid pair format."""
        result = admin_service.update_markup_rate("INVALID", 5.0)
        assert result is False

    def test_format_markup_info_message_with_pairs(self, admin_service):
        """Test formatting markup info message with pairs."""
        message = admin_service.format_markup_info_message()
        assert "Текущие наценки" in message  # Without HTML tags
        assert "RUB/ZAR" in message
        assert "3.0%" in message
        assert "USDT/THB" in message
        assert "2.0%" in message
        assert "2.5%" in message  # Default markup without HTML

    def test_format_markup_info_message_empty(self, mock_settings):
        """Test formatting markup info message with no pairs."""
        mock_settings.currency_pairs = {}
        service = AdminService(mock_settings)
        message = service.format_markup_info_message()
        assert "Валютные пары не настроены" in message
        assert "2.5%" in message  # Default markup without HTML

    def test_format_markup_change_message(self, admin_service):
        """Test formatting markup change confirmation message."""
        message = admin_service.format_markup_change_message("RUB/ZAR", 3.0, 5.0)
        assert "Наценка обновлена" in message
        assert "RUB/ZAR" in message
        assert "3.0%" in message
        assert "5.0%" in message


class TestGetAdminService:
    """Test get_admin_service function."""

    def test_get_admin_service_singleton(self, mock_settings):
        """Test that get_admin_service returns singleton instance."""
        service1 = get_admin_service(mock_settings)
        service2 = get_admin_service(mock_settings)
        assert service1 is service2


class TestCheckAdminAccess:
    """Test check_admin_access function."""

    @pytest.mark.asyncio
    async def test_check_admin_access_admin_user_message(
        self, mock_admin_user, mock_chat, mock_settings
    ):
        """Test check_admin_access with admin user and message."""
        message = MagicMock(spec=Message)
        message.from_user = mock_admin_user
        message.answer = AsyncMock()

        result = await check_admin_access(message, mock_settings)
        assert result is True
        message.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_admin_access_non_admin_user_message(
        self, mock_regular_user, mock_chat, mock_settings
    ):
        """Test check_admin_access with non-admin user and message."""
        message = MagicMock(spec=Message)
        message.from_user = mock_regular_user
        message.answer = AsyncMock()

        result = await check_admin_access(message, mock_settings)
        assert result is False
        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        assert "Доступ запрещен" in args[0]
        assert kwargs["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_check_admin_access_admin_user_callback(
        self, mock_admin_user, mock_settings
    ):
        """Test check_admin_access with admin user and callback query."""
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = mock_admin_user
        callback.answer = AsyncMock()

        result = await check_admin_access(callback, mock_settings)
        assert result is True
        callback.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_admin_access_non_admin_user_callback(
        self, mock_regular_user, mock_settings
    ):
        """Test check_admin_access with non-admin user and callback query."""
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = mock_regular_user
        callback.answer = AsyncMock()

        result = await check_admin_access(callback, mock_settings)
        assert result is False
        callback.answer.assert_called_once_with("❌ Доступ запрещен", show_alert=True)


class TestCommandHandlers:
    """Test command handler functions."""

    @pytest.mark.asyncio
    async def test_cmd_set_markup_admin_access(self, mock_message, mock_settings):
        """Test /set_markup command with admin access."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.format_markup_info_message.return_value = "Test message"
                mock_get_service.return_value = mock_service

                with patch(
                    "bot.handlers.admin_handlers.CurrencyKeyboard"
                ) as mock_keyboard:
                    mock_keyboard_instance = MagicMock()
                    mock_keyboard_instance.create_markup_selection_keyboard.return_value = (
                        MagicMock()
                    )
                    mock_keyboard.return_value = mock_keyboard_instance

                    await cmd_set_markup(mock_message, mock_settings)

                    mock_check_admin.assert_called_once_with(
                        mock_message, mock_settings
                    )
                    mock_message.answer.assert_called_once()
                    args, kwargs = mock_message.answer.call_args
                    assert "Test message" in args[0]
                    assert kwargs["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_cmd_set_markup_non_admin_access(self, mock_settings):
        """Test /set_markup command with non-admin access."""
        # Create message from non-admin user
        message = MagicMock(spec=Message)
        message.from_user = User(id=987654321, is_bot=False, first_name="Regular")
        message.answer = AsyncMock()

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = False

            await cmd_set_markup(message, mock_settings)

            mock_check_admin.assert_called_once_with(message, mock_settings)

    @pytest.mark.asyncio
    async def test_cmd_set_markup_exception(self, mock_message, mock_settings):
        """Test /set_markup command with exception."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.format_markup_info_message.side_effect = Exception(
                    "Test error"
                )
                mock_get_service.return_value = mock_service

                await cmd_set_markup(mock_message, mock_settings)

                mock_message.answer.assert_called_once()
                args, kwargs = mock_message.answer.call_args
                assert "Произошла ошибка" in args[0]


class TestCallbackHandlers:
    """Test callback handler functions."""

    @pytest.mark.asyncio
    async def test_handle_markup_selection_valid_data(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test markup selection with valid callback data."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.get_current_markup.return_value = 3.0
                mock_get_service.return_value = mock_service

                with patch("bot.handlers.admin_handlers.parse_callback") as mock_parse:
                    mock_parse.return_value = ("markup", "RUB", "ZAR")

                    await handle_markup_selection(
                        mock_callback_query, mock_settings, mock_fsm_context
                    )

                    mock_check_admin.assert_called_once_with(
                        mock_callback_query, mock_settings
                    )
                    mock_fsm_context.update_data.assert_called_once()
                    mock_fsm_context.set_state.assert_called_once_with(
                        AdminStates.waiting_for_markup_value
                    )
                    mock_callback_query.message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_markup_selection_invalid_data(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test markup selection with invalid callback data."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch("bot.handlers.admin_handlers.parse_callback") as mock_parse:
                mock_parse.return_value = None

                await handle_markup_selection(
                    mock_callback_query, mock_settings, mock_fsm_context
                )

                mock_callback_query.answer.assert_called_once_with(
                    "❌ Неверный формат данных", show_alert=True
                )

    @pytest.mark.asyncio
    async def test_handle_markup_selection_wrong_action(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test markup selection with wrong action in callback data."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch("bot.handlers.admin_handlers.parse_callback") as mock_parse:
                mock_parse.return_value = ("wrong", "RUB", "ZAR")

                await handle_markup_selection(
                    mock_callback_query, mock_settings, mock_fsm_context
                )

                mock_callback_query.answer.assert_called_once_with(
                    "❌ Неверное действие", show_alert=True
                )


class TestMarkupValueInput:
    """Test markup value input handler."""

    @pytest.mark.asyncio
    async def test_handle_markup_value_input_valid(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test markup value input with valid value."""
        mock_message.text = "5.5"
        mock_fsm_context.get_data.return_value = {
            "pair_string": "RUB/ZAR",
            "current_markup": 3.0,
        }

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.update_markup_rate.return_value = True
                mock_service.format_markup_change_message.return_value = (
                    "Success message"
                )
                mock_service.format_markup_info_message.return_value = "Info message"
                mock_get_service.return_value = mock_service

                with patch(
                    "bot.handlers.admin_handlers.CurrencyKeyboard"
                ) as mock_keyboard:
                    mock_keyboard_instance = MagicMock()
                    mock_keyboard_instance.create_markup_selection_keyboard.return_value = (
                        MagicMock()
                    )
                    mock_keyboard.return_value = mock_keyboard_instance

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        await handle_markup_value_input(
                            mock_message, mock_settings, mock_fsm_context
                        )

                    mock_check_admin.assert_called_once_with(
                        mock_message, mock_settings
                    )
                    mock_service.update_markup_rate.assert_called_once_with(
                        "RUB/ZAR", 5.5
                    )
                    assert (
                        mock_message.answer.call_count == 2
                    )  # Success + info messages
                    mock_fsm_context.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_markup_value_input_invalid_format(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test markup value input with invalid format."""
        mock_message.text = "invalid"
        mock_fsm_context.get_data.return_value = {
            "pair_string": "RUB/ZAR",
            "current_markup": 3.0,
        }

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            await handle_markup_value_input(
                mock_message, mock_settings, mock_fsm_context
            )

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "Неверный формат" in args[0]

    @pytest.mark.asyncio
    async def test_handle_markup_value_input_out_of_range(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test markup value input with out of range value."""
        mock_message.text = "150"
        mock_fsm_context.get_data.return_value = {
            "pair_string": "RUB/ZAR",
            "current_markup": 3.0,
        }

        with patch("bot.handlers.admin_handlers.get_admin_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_admin.return_value = True
            mock_get_service.return_value = mock_service

            await handle_markup_value_input(
                mock_message, mock_settings, mock_fsm_context
            )

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "Значение вне диапазона" in args[0]

    @pytest.mark.asyncio
    async def test_handle_markup_value_input_no_session_data(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test markup value input with no session data."""
        mock_message.text = "5.0"
        mock_fsm_context.get_data.return_value = {}

        with patch("bot.handlers.admin_handlers.get_admin_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_admin.return_value = True
            mock_get_service.return_value = mock_service

            await handle_markup_value_input(
                mock_message, mock_settings, mock_fsm_context
            )

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "данные сессии потеряны" in args[0]
            mock_fsm_context.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_markup_value_input_update_failed(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test markup value input when update fails."""
        mock_message.text = "5.0"
        mock_fsm_context.get_data.return_value = {
            "pair_string": "RUB/ZAR",
            "current_markup": 3.0,
        }

        with patch("bot.handlers.admin_handlers.get_admin_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_admin.return_value = True
            mock_service.update_markup_rate.return_value = False
            mock_get_service.return_value = mock_service

            await handle_markup_value_input(
                mock_message, mock_settings, mock_fsm_context
            )

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "Ошибка обновления" in args[0]


class TestBackNavigation:
    """Test back navigation handler."""

    @pytest.mark.asyncio
    async def test_handle_back_to_markup_selection(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test back to markup selection."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.format_markup_info_message.return_value = "Info message"
                mock_get_service.return_value = mock_service

                with patch(
                    "bot.handlers.admin_handlers.CurrencyKeyboard"
                ) as mock_keyboard:
                    mock_keyboard_instance = MagicMock()
                    mock_keyboard_instance.create_markup_selection_keyboard.return_value = (
                        MagicMock()
                    )
                    mock_keyboard.return_value = mock_keyboard_instance

                    await handle_back_to_markup_selection(
                        mock_callback_query, mock_settings, mock_fsm_context
                    )

                    mock_check_admin.assert_called_once_with(
                        mock_callback_query, mock_settings
                    )
                    mock_fsm_context.clear.assert_called_once()
                    mock_callback_query.message.edit_text.assert_called_once()
                    mock_callback_query.answer.assert_called_once()


class TestAdminStates:
    """Test AdminStates FSM states."""

    def test_admin_states_defined(self):
        """Test that AdminStates are properly defined."""
        assert hasattr(AdminStates, "waiting_for_markup_value")
        from aiogram.fsm.state import State

        assert isinstance(AdminStates.waiting_for_markup_value, State)
