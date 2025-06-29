"""Unit tests for set_manager command handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.fsm.context import FSMContext

from bot.handlers.admin_handlers import (
    AdminService,
    AdminStates,
    cmd_set_manager,
    handle_manager_selection,
    handle_manager_id_input,
    handle_back_to_manager_selection,
)
from config.models import Settings, TelegramConfig, CurrencyPair, ManagerConfig


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Settings()
    settings.telegram = TelegramConfig(admin_user_ids=[123456789])
    settings.default_manager_id = 999999999

    # Add some test currency pairs
    settings.currency_pairs = {
        "RUB/ZAR": CurrencyPair(base="RUB", quote="ZAR", markup_rate=3.0),
        "USDT/THB": CurrencyPair(base="USDT", quote="THB", markup_rate=2.0),
    }

    # Add some test managers
    settings.managers = {
        111111111: ManagerConfig(
            user_id=111111111, name="Менеджер Иван", currency_pairs={"RUB/ZAR"}
        ),
        222222222: ManagerConfig(
            user_id=222222222, name="Менеджер Петр", currency_pairs={"USDT/THB"}
        ),
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
    message.text = "333333333"
    return message


@pytest.fixture
def mock_callback_query(mock_admin_user):
    """Create mock callback query from admin user."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = mock_admin_user
    callback.data = "manager:RUB:ZAR"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    return callback


@pytest.fixture
def mock_fsm_context():
    """Create mock FSM context."""
    context = MagicMock(spec=FSMContext)
    context.get_data = AsyncMock(
        return_value={
            "pair_string": "RUB/ZAR",
            "current_manager_id": 111111111,
            "current_manager_name": "Менеджер Иван",
        }
    )
    context.update_data = AsyncMock()
    context.set_state = AsyncMock()
    context.clear = AsyncMock()
    return context


class TestAdminServiceManagerMethods:
    """Test AdminService manager-related methods."""

    def test_get_current_manager_with_assigned_manager(self, admin_service):
        """Test getting current manager when manager is assigned."""
        manager_id = admin_service.get_current_manager("RUB/ZAR")
        assert manager_id == 111111111

    def test_get_current_manager_with_default_manager(self, admin_service):
        """Test getting current manager when only default manager exists."""
        manager_id = admin_service.get_current_manager("EUR/USD")  # Non-existing pair
        assert manager_id == 999999999  # default_manager_id

    def test_get_current_manager_no_manager(self, mock_settings):
        """Test getting current manager when no manager assigned."""
        mock_settings.default_manager_id = None
        service = AdminService(mock_settings)
        manager_id = service.get_current_manager("EUR/USD")
        assert manager_id is None

    def test_get_manager_name_existing_manager(self, admin_service):
        """Test getting name of existing manager."""
        name = admin_service.get_manager_name(111111111)
        assert name == "Менеджер Иван"

    def test_get_manager_name_default_manager(self, admin_service):
        """Test getting name of default manager."""
        name = admin_service.get_manager_name(999999999)
        assert name == "Менеджер по умолчанию"

    def test_get_manager_name_unknown_manager(self, admin_service):
        """Test getting name of unknown manager."""
        name = admin_service.get_manager_name(888888888)
        assert name == "Неизвестный менеджер"

    def test_assign_manager_to_pair_new_manager(self, admin_service):
        """Test assigning new manager to existing pair."""
        success = admin_service.assign_manager_to_pair(
            "RUB/ZAR", 333333333, "Новый Менеджер"
        )
        assert success is True
        assert 333333333 in admin_service.settings.managers
        assert "RUB/ZAR" in admin_service.settings.managers[333333333].currency_pairs

    def test_assign_manager_to_pair_existing_manager(self, admin_service):
        """Test assigning existing manager to new pair."""
        success = admin_service.assign_manager_to_pair("EUR/USD", 111111111, "")
        assert success is True
        assert "EUR/USD" in admin_service.settings.managers[111111111].currency_pairs

    def test_assign_manager_to_pair_invalid_id(self, admin_service):
        """Test assigning manager with invalid ID."""
        success = admin_service.assign_manager_to_pair("RUB/ZAR", -1, "Invalid Manager")
        assert success is False

    def test_assign_manager_to_pair_invalid_pair_format(self, admin_service):
        """Test assigning manager to invalid pair format."""
        success = admin_service.assign_manager_to_pair("INVALID", 333333333, "Manager")
        assert success is False

    def test_assign_manager_removes_from_other_managers(self, admin_service):
        """Test that assigning manager removes pair from other managers."""
        # Initially RUB/ZAR is assigned to manager 111111111
        assert "RUB/ZAR" in admin_service.settings.managers[111111111].currency_pairs

        # Assign to different manager
        success = admin_service.assign_manager_to_pair("RUB/ZAR", 222222222, "")
        assert success is True

        # Should be removed from old manager and added to new one
        assert (
            "RUB/ZAR" not in admin_service.settings.managers[111111111].currency_pairs
        )
        assert "RUB/ZAR" in admin_service.settings.managers[222222222].currency_pairs

    def test_format_managers_info_message_with_managers(self, admin_service):
        """Test formatting managers info message with assigned managers."""
        message = admin_service.format_managers_info_message()
        assert "Текущие назначения менеджеров" in message
        assert "RUB/ZAR" in message
        assert "Менеджер Иван" in message
        assert "111111111" in message
        assert "USDT/THB" in message
        assert "Менеджер Петр" in message
        assert "222222222" in message
        assert "Менеджер по умолчанию" in message
        assert "999999999" in message

    def test_format_managers_info_message_empty(self, mock_settings):
        """Test formatting managers info message with no pairs."""
        mock_settings.currency_pairs = {}
        mock_settings.managers = {}
        service = AdminService(mock_settings)
        message = service.format_managers_info_message()
        assert "Валютные пары не настроены" in message
        assert "Менеджер по умолчанию" in message
        assert "999999999" in message

    def test_format_manager_change_message(self, admin_service):
        """Test formatting manager change confirmation message."""
        message = admin_service.format_manager_change_message(
            "RUB/ZAR", 111111111, 333333333, "Новый Менеджер"
        )
        assert "Менеджер назначен" in message
        assert "RUB/ZAR" in message
        assert "Менеджер Иван" in message
        assert "Новый Менеджер" in message
        assert "333333333" in message

    def test_format_manager_change_message_no_old_manager(self, admin_service):
        """Test formatting manager change message with no previous manager."""
        message = admin_service.format_manager_change_message(
            "EUR/USD", None, 333333333, "Новый Менеджер"
        )
        assert "Менеджер назначен" in message
        assert "EUR/USD" in message
        assert "Не назначен" in message
        assert "Новый Менеджер" in message
        assert "333333333" in message


class TestSetManagerCommand:
    """Test /set_manager command handler."""

    @pytest.mark.asyncio
    async def test_cmd_set_manager_admin_access(self, mock_message, mock_settings):
        """Test /set_manager command with admin access."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.format_managers_info_message.return_value = (
                    "Test managers message"
                )
                mock_get_service.return_value = mock_service

                with patch(
                    "bot.handlers.admin_handlers.CurrencyKeyboard"
                ) as mock_keyboard:
                    mock_keyboard_instance = MagicMock()
                    mock_keyboard_instance.create_manager_selection_keyboard.return_value = (
                        MagicMock()
                    )
                    mock_keyboard.return_value = mock_keyboard_instance

                    await cmd_set_manager(mock_message, mock_settings)

                    mock_check_admin.assert_called_once_with(
                        mock_message, mock_settings
                    )
                    mock_message.answer.assert_called_once()
                    args, kwargs = mock_message.answer.call_args
                    assert "Test managers message" in args[0]
                    assert kwargs["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_cmd_set_manager_non_admin_access(self, mock_settings):
        """Test /set_manager command with non-admin access."""
        message = MagicMock(spec=Message)
        message.from_user = User(id=987654321, is_bot=False, first_name="Regular")
        message.answer = AsyncMock()

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = False

            await cmd_set_manager(message, mock_settings)

            mock_check_admin.assert_called_once_with(message, mock_settings)

    @pytest.mark.asyncio
    async def test_cmd_set_manager_exception(self, mock_message, mock_settings):
        """Test /set_manager command with exception."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.format_managers_info_message.side_effect = Exception(
                    "Test error"
                )
                mock_get_service.return_value = mock_service

                await cmd_set_manager(mock_message, mock_settings)

                mock_message.answer.assert_called_once()
                args, kwargs = mock_message.answer.call_args
                assert "Произошла ошибка" in args[0]


class TestManagerSelection:
    """Test manager selection callback handler."""

    @pytest.mark.asyncio
    async def test_handle_manager_selection_valid_data(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test manager selection with valid callback data."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.get_current_manager.return_value = 111111111
                mock_service.get_manager_name.return_value = "Менеджер Иван"
                mock_get_service.return_value = mock_service

                with patch("bot.handlers.admin_handlers.parse_callback") as mock_parse:
                    mock_parse.return_value = ("manager", "RUB", "ZAR")

                    await handle_manager_selection(
                        mock_callback_query, mock_settings, mock_fsm_context
                    )

                    mock_check_admin.assert_called_once_with(
                        mock_callback_query, mock_settings
                    )
                    mock_fsm_context.update_data.assert_called_once()
                    mock_fsm_context.set_state.assert_called_once_with(
                        AdminStates.waiting_for_manager_id
                    )
                    mock_callback_query.message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_manager_selection_invalid_data(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test manager selection with invalid callback data."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch("bot.handlers.admin_handlers.parse_callback") as mock_parse:
                mock_parse.return_value = None

                await handle_manager_selection(
                    mock_callback_query, mock_settings, mock_fsm_context
                )

                mock_callback_query.answer.assert_called_once_with(
                    "❌ Неверный формат данных", show_alert=True
                )

    @pytest.mark.asyncio
    async def test_handle_manager_selection_wrong_action(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test manager selection with wrong action in callback data."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch("bot.handlers.admin_handlers.parse_callback") as mock_parse:
                mock_parse.return_value = ("wrong", "RUB", "ZAR")

                await handle_manager_selection(
                    mock_callback_query, mock_settings, mock_fsm_context
                )

                mock_callback_query.answer.assert_called_once_with(
                    "❌ Неверное действие", show_alert=True
                )


class TestManagerIdInput:
    """Test manager ID input handler."""

    @pytest.mark.asyncio
    async def test_handle_manager_id_input_valid(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test manager ID input with valid ID."""
        mock_message.text = "333333333"

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.assign_manager_to_pair.return_value = True
                mock_service.format_manager_change_message.return_value = (
                    "Success message"
                )
                mock_service.format_managers_info_message.return_value = "Info message"
                mock_get_service.return_value = mock_service

                with patch(
                    "bot.handlers.admin_handlers.CurrencyKeyboard"
                ) as mock_keyboard:
                    mock_keyboard_instance = MagicMock()
                    mock_keyboard_instance.create_manager_selection_keyboard.return_value = (
                        MagicMock()
                    )
                    mock_keyboard.return_value = mock_keyboard_instance

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        await handle_manager_id_input(
                            mock_message, mock_settings, mock_fsm_context
                        )

                    mock_check_admin.assert_called_once_with(
                        mock_message, mock_settings
                    )
                    mock_service.assign_manager_to_pair.assert_called_once_with(
                        "RUB/ZAR", 333333333, "Менеджер 333333333"
                    )
                    assert (
                        mock_message.answer.call_count == 2
                    )  # Success + info messages
                    mock_fsm_context.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_manager_id_input_invalid_format(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test manager ID input with invalid format."""
        mock_message.text = "invalid_id"

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            await handle_manager_id_input(mock_message, mock_settings, mock_fsm_context)

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "Неверный формат" in args[0]

    @pytest.mark.asyncio
    async def test_handle_manager_id_input_negative_id(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test manager ID input with negative ID."""
        mock_message.text = "-123"

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            await handle_manager_id_input(mock_message, mock_settings, mock_fsm_context)

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "Неверный ID" in args[0]

    @pytest.mark.asyncio
    async def test_handle_manager_id_input_zero_id(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test manager ID input with zero ID."""
        mock_message.text = "0"

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            await handle_manager_id_input(mock_message, mock_settings, mock_fsm_context)

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "Неверный ID" in args[0]

    @pytest.mark.asyncio
    async def test_handle_manager_id_input_no_session_data(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test manager ID input with no session data."""
        mock_message.text = "333333333"
        mock_fsm_context.get_data.return_value = {}

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            await handle_manager_id_input(mock_message, mock_settings, mock_fsm_context)

            mock_message.answer.assert_called_once()
            args, kwargs = mock_message.answer.call_args
            assert "данные сессии потеряны" in args[0]
            mock_fsm_context.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_manager_id_input_assignment_failed(
        self, mock_message, mock_settings, mock_fsm_context
    ):
        """Test manager ID input when assignment fails."""
        mock_message.text = "333333333"

        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.assign_manager_to_pair.return_value = False
                mock_get_service.return_value = mock_service

                await handle_manager_id_input(
                    mock_message, mock_settings, mock_fsm_context
                )

                mock_message.answer.assert_called_once()
                args, kwargs = mock_message.answer.call_args
                assert "Ошибка назначения" in args[0]


class TestBackNavigation:
    """Test back navigation handler."""

    @pytest.mark.asyncio
    async def test_handle_back_to_manager_selection(
        self, mock_callback_query, mock_settings, mock_fsm_context
    ):
        """Test back to manager selection."""
        with patch(
            "bot.handlers.admin_handlers.check_admin_access"
        ) as mock_check_admin:
            mock_check_admin.return_value = True

            with patch(
                "bot.handlers.admin_handlers.get_admin_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.format_managers_info_message.return_value = "Info message"
                mock_get_service.return_value = mock_service

                with patch(
                    "bot.handlers.admin_handlers.CurrencyKeyboard"
                ) as mock_keyboard:
                    mock_keyboard_instance = MagicMock()
                    mock_keyboard_instance.create_manager_selection_keyboard.return_value = (
                        MagicMock()
                    )
                    mock_keyboard.return_value = mock_keyboard_instance

                    await handle_back_to_manager_selection(
                        mock_callback_query, mock_settings, mock_fsm_context
                    )

                    mock_check_admin.assert_called_once_with(
                        mock_callback_query, mock_settings
                    )
                    mock_fsm_context.clear.assert_called_once()
                    mock_callback_query.message.edit_text.assert_called_once()
                    mock_callback_query.answer.assert_called_once()


class TestAdminStatesExtended:
    """Test extended AdminStates FSM states."""

    def test_admin_states_manager_defined(self):
        """Test that manager-related AdminStates are properly defined."""
        assert hasattr(AdminStates, "waiting_for_manager_id")
        assert isinstance(
            AdminStates.waiting_for_manager_id,
            type(AdminStates.waiting_for_manager_id),
        )
