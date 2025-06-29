"""Unit tests for currency keyboard module."""

from unittest.mock import Mock

from src.bot.keyboards.currency_keyboard import (
    CurrencyKeyboard,
    get_rate_keyboard,
    get_calc_keyboard,
    get_admin_keyboard,
    parse_callback,
)
from src.config.models import Settings, CurrencyPair, ManagerConfig


class TestCurrencyKeyboard:
    """Test cases for CurrencyKeyboard class."""

    def test_init_without_settings(self):
        """Test initialization without settings uses default pairs."""
        keyboard = CurrencyKeyboard()

        assert keyboard.settings is None
        assert len(keyboard._currency_pairs) == 8
        assert ("RUB", "ZAR") in keyboard._currency_pairs
        assert ("USDT", "IDR") in keyboard._currency_pairs

    def test_init_with_settings(self):
        """Test initialization with settings uses configured pairs."""
        # Create mock settings with currency pairs
        settings = Mock(spec=Settings)
        pair1 = CurrencyPair(base="BTC", quote="USD", is_active=True)
        pair2 = CurrencyPair(base="ETH", quote="EUR", is_active=True)
        settings.get_active_currency_pairs.return_value = [pair1, pair2]
        settings.currency_pairs = {"BTC/USD": pair1, "ETH/EUR": pair2}

        keyboard = CurrencyKeyboard(settings)

        assert keyboard.settings == settings
        assert len(keyboard._currency_pairs) == 2
        assert ("BTC", "USD") in keyboard._currency_pairs
        assert ("ETH", "EUR") in keyboard._currency_pairs

    def test_get_currency_pairs_with_empty_settings(self):
        """Test _get_currency_pairs with empty settings returns defaults."""
        settings = Mock(spec=Settings)
        settings.currency_pairs = {}
        settings.get_active_currency_pairs.return_value = []

        keyboard = CurrencyKeyboard(settings)

        assert len(keyboard._currency_pairs) == 8
        assert keyboard._currency_pairs == CurrencyKeyboard.DEFAULT_CURRENCY_PAIRS

    def test_format_currency_button_text(self):
        """Test currency button text formatting with emojis."""
        keyboard = CurrencyKeyboard()

        text = keyboard._format_currency_button_text("RUB", "ZAR")
        assert text == "🇷🇺 RUB → ZAR 🇿🇦"

        text = keyboard._format_currency_button_text("USDT", "THB")
        assert text == "💰 USDT → THB 🇹🇭"

    def test_format_currency_button_text_unknown_currency(self):
        """Test formatting with unknown currency codes."""
        keyboard = CurrencyKeyboard()

        text = keyboard._format_currency_button_text("BTC", "USD")
        assert text == "₿ BTC → USD 🇺🇸"

    def test_create_callback_data(self):
        """Test callback data creation."""
        keyboard = CurrencyKeyboard()

        callback = keyboard._create_callback_data("RUB", "ZAR")
        assert callback == "currency:RUB:ZAR"

        callback = keyboard._create_callback_data("USDT", "IDR")
        assert callback == "currency:USDT:IDR"

    def test_create_rate_selection_keyboard(self):
        """Test rate selection keyboard creation."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_rate_selection_keyboard()

        # Should have 8 buttons (8 pairs × 1 direction)
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 8

        # Check first row has 2 buttons (2-column layout)
        assert len(markup.inline_keyboard[0]) == 2

        # Check button content
        first_button = markup.inline_keyboard[0][0]
        assert "RUB → ZAR" in first_button.text
        assert first_button.callback_data == "currency:RUB:ZAR"

    def test_create_calc_selection_keyboard(self):
        """Test calc selection keyboard creation."""
        keyboard = CurrencyKeyboard()
        calc_markup = keyboard.create_calc_selection_keyboard()
        rate_markup = keyboard.create_rate_selection_keyboard()

        # Should be identical to rate selection keyboard
        assert len(calc_markup.inline_keyboard) == len(rate_markup.inline_keyboard)

        # Compare first button
        assert (
            calc_markup.inline_keyboard[0][0].text
            == rate_markup.inline_keyboard[0][0].text
        )
        assert (
            calc_markup.inline_keyboard[0][0].callback_data
            == rate_markup.inline_keyboard[0][0].callback_data
        )

    def test_create_admin_currency_keyboard(self):
        """Test admin currency keyboard creation."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_admin_currency_keyboard()

        # Should have 8 currency pair buttons + 2 management buttons
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 10

        # Check management buttons in last row
        last_row = markup.inline_keyboard[-1]
        assert len(last_row) == 2
        assert "Добавить пару" in last_row[0].text
        assert "Обновить" in last_row[1].text
        assert last_row[0].callback_data == "admin:add_pair"
        assert last_row[1].callback_data == "admin:refresh_pairs"

    def test_create_markup_selection_keyboard_without_settings(self):
        """Test markup selection keyboard without settings."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_markup_selection_keyboard()

        # Should have 8 buttons for currency pairs
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 8

        # Check default markup rate
        first_button = markup.inline_keyboard[0][0]
        assert "RUB/ZAR (2.5%)" in first_button.text
        assert first_button.callback_data == "markup:RUB:ZAR"

    def test_create_markup_selection_keyboard_with_settings(self):
        """Test markup selection keyboard with custom settings."""
        # Create mock settings
        settings = Mock(spec=Settings)
        settings.currency_pairs = {}
        settings.get_active_currency_pairs.return_value = []

        pair_config = Mock(spec=CurrencyPair)
        pair_config.markup_rate = 3.5
        settings.get_currency_pair.return_value = pair_config

        keyboard = CurrencyKeyboard(settings)
        markup = keyboard.create_markup_selection_keyboard()

        # Check custom markup rate
        first_button = markup.inline_keyboard[0][0]
        assert "(3.5%)" in first_button.text

    def test_create_manager_selection_keyboard_without_settings(self):
        """Test manager selection keyboard without settings."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_manager_selection_keyboard()

        # Should have 8 buttons for currency pairs
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 8

        # Check default manager status
        first_button = markup.inline_keyboard[0][0]
        assert "RUB/ZAR (Не назначен)" in first_button.text
        assert first_button.callback_data == "manager:RUB:ZAR"

    def test_create_manager_selection_keyboard_with_managers(self):
        """Test manager selection keyboard with assigned managers."""
        # Create mock settings with managers
        settings = Mock(spec=Settings)
        settings.currency_pairs = {}
        settings.get_active_currency_pairs.return_value = []
        settings.default_manager_id = 999999999

        # Mock manager for specific pair
        manager = Mock()
        manager.user_id = 123456789
        settings.get_manager_for_pair.return_value = manager

        keyboard = CurrencyKeyboard(settings)
        markup = keyboard.create_manager_selection_keyboard()

        # Check manager ID display
        first_button = markup.inline_keyboard[0][0]
        assert "(ID: 123456789)" in first_button.text

    def test_create_manager_selection_keyboard_with_default_manager(self):
        """Test manager selection keyboard with default manager only."""
        # Create mock settings with default manager
        settings = Mock(spec=Settings)
        settings.currency_pairs = {}
        settings.get_active_currency_pairs.return_value = []
        settings.default_manager_id = 999999999

        # No specific manager for pair
        settings.get_manager_for_pair.return_value = None

        keyboard = CurrencyKeyboard(settings)
        markup = keyboard.create_manager_selection_keyboard()

        # Check default manager display
        first_button = markup.inline_keyboard[0][0]
        assert "(По умолчанию: 999999999)" in first_button.text

    def test_create_manager_selection_keyboard_no_managers(self):
        """Test manager selection keyboard with no managers."""
        # Create mock settings without managers
        settings = Mock(spec=Settings)
        settings.currency_pairs = {}
        settings.get_active_currency_pairs.return_value = []
        settings.default_manager_id = None
        settings.get_manager_for_pair.return_value = None

        keyboard = CurrencyKeyboard(settings)
        markup = keyboard.create_manager_selection_keyboard()

        # Check unassigned status
        first_button = markup.inline_keyboard[0][0]
        assert "(Не назначен)" in first_button.text

    def test_manager_selection_keyboard_callback_format(self):
        """Test manager selection keyboard callback data format."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_manager_selection_keyboard()

        # Check callback data format
        for row in markup.inline_keyboard:
            for button in row:
                assert button.callback_data.startswith("manager:")
                # Should be in format "manager:BASE:QUOTE"
                parts = button.callback_data.split(":")
                assert len(parts) == 3
                assert parts[0] == "manager"

    def test_manager_selection_keyboard_layout(self):
        """Test manager selection keyboard layout."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_manager_selection_keyboard()

        # Check 2-column layout (mobile optimization)
        for row in markup.inline_keyboard:
            assert len(row) <= 2, "Row has more than 2 buttons"

        # Should have 4 rows (8 buttons ÷ 2 columns)
        assert len(markup.inline_keyboard) == 4

    def test_parse_currency_callback_valid(self):
        """Test parsing valid currency callback data."""
        result = CurrencyKeyboard.parse_currency_callback("currency:RUB:ZAR")
        assert result == ("currency", "RUB", "ZAR")

        result = CurrencyKeyboard.parse_currency_callback("markup:USDT:THB")
        assert result == ("markup", "USDT", "THB")

        result = CurrencyKeyboard.parse_currency_callback("admin:currency:BTC:USD")
        assert result == ("admin", "currency", "BTC")

    def test_parse_currency_callback_invalid(self):
        """Test parsing invalid currency callback data."""
        result = CurrencyKeyboard.parse_currency_callback("invalid")
        assert result is None

        result = CurrencyKeyboard.parse_currency_callback("currency:RUB")
        assert result is None

        result = CurrencyKeyboard.parse_currency_callback("")
        assert result is None

        result = CurrencyKeyboard.parse_currency_callback("currency:")
        assert result is None

    def test_create_back_keyboard(self):
        """Test back button keyboard creation."""
        markup = CurrencyKeyboard.create_back_keyboard()

        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 1

        button = markup.inline_keyboard[0][0]
        assert "Назад" in button.text
        assert button.callback_data == "back"

    def test_create_back_keyboard_custom_callback(self):
        """Test back button keyboard with custom callback."""
        markup = CurrencyKeyboard.create_back_keyboard("custom_back")

        button = markup.inline_keyboard[0][0]
        assert button.callback_data == "custom_back"

    def test_create_confirm_keyboard(self):
        """Test confirmation keyboard creation."""
        markup = CurrencyKeyboard.create_confirm_keyboard()

        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 2

        confirm_button = markup.inline_keyboard[0][0]
        cancel_button = markup.inline_keyboard[0][1]

        assert "Подтвердить" in confirm_button.text
        assert "Отмена" in cancel_button.text
        assert confirm_button.callback_data == "confirm"
        assert cancel_button.callback_data == "cancel"

    def test_create_confirm_keyboard_custom_callbacks(self):
        """Test confirmation keyboard with custom callbacks."""
        markup = CurrencyKeyboard.create_confirm_keyboard("yes", "no")

        confirm_button = markup.inline_keyboard[0][0]
        cancel_button = markup.inline_keyboard[0][1]

        assert confirm_button.callback_data == "yes"
        assert cancel_button.callback_data == "no"

    def test_currency_emojis_mapping(self):
        """Test currency emoji mapping completeness."""
        emojis = CurrencyKeyboard.CURRENCY_EMOJIS

        # Check all default currencies have emojis
        for base, quote in CurrencyKeyboard.DEFAULT_CURRENCY_PAIRS:
            assert base in emojis, f"Missing emoji for {base}"
            assert quote in emojis, f"Missing emoji for {quote}"

        # Check emoji values are not empty
        for currency, emoji in emojis.items():
            assert emoji, f"Empty emoji for {currency}"

    def test_default_currency_pairs_structure(self):
        """Test default currency pairs structure."""
        pairs = CurrencyKeyboard.DEFAULT_CURRENCY_PAIRS

        assert len(pairs) == 8

        # Check all pairs are tuples with 2 elements
        for pair in pairs:
            assert isinstance(pair, tuple)
            assert len(pair) == 2
            assert isinstance(pair[0], str)
            assert isinstance(pair[1], str)
            assert len(pair[0]) >= 3  # Currency codes are at least 3 chars
            assert len(pair[1]) >= 3


class TestConvenienceFunctions:
    """Test cases for convenience functions."""

    def test_get_rate_keyboard(self):
        """Test get_rate_keyboard convenience function."""
        markup = get_rate_keyboard()

        # Should return InlineKeyboardMarkup
        assert hasattr(markup, "inline_keyboard")

        # Should have 8 buttons (8 pairs × 1 direction)
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 8

    def test_get_rate_keyboard_with_settings(self):
        """Test get_rate_keyboard with settings."""
        settings = Mock(spec=Settings)
        pair1 = CurrencyPair(base="BTC", quote="USD", is_active=True)
        settings.get_active_currency_pairs.return_value = [pair1]
        settings.currency_pairs = {"BTC/USD": pair1}

        markup = get_rate_keyboard(settings)

        # Should have 1 button (1 pair × 1 direction)
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 1

    def test_get_calc_keyboard(self):
        """Test get_calc_keyboard convenience function."""
        markup = get_calc_keyboard()

        # Should return InlineKeyboardMarkup
        assert hasattr(markup, "inline_keyboard")

        # Should have same structure as rate keyboard
        rate_markup = get_rate_keyboard()
        assert len(markup.inline_keyboard) == len(rate_markup.inline_keyboard)

    def test_get_admin_keyboard(self):
        """Test get_admin_keyboard convenience function."""
        markup = get_admin_keyboard()

        # Should return InlineKeyboardMarkup with admin features
        assert hasattr(markup, "inline_keyboard")

        # Should have management buttons
        last_row = markup.inline_keyboard[-1]
        assert any("Добавить" in button.text for button in last_row)

    def test_parse_callback(self):
        """Test parse_callback convenience function."""
        result = parse_callback("currency:RUB:ZAR")
        assert result == ("currency", "RUB", "ZAR")

        result = parse_callback("invalid")
        assert result is None


class TestKeyboardIntegration:
    """Integration tests for keyboard functionality."""

    def test_keyboard_button_consistency(self):
        """Test consistency between different keyboard types."""
        keyboard = CurrencyKeyboard()

        rate_markup = keyboard.create_rate_selection_keyboard()
        calc_markup = keyboard.create_calc_selection_keyboard()

        # Both should have same number of currency buttons
        rate_buttons = sum(len(row) for row in rate_markup.inline_keyboard)
        calc_buttons = sum(len(row) for row in calc_markup.inline_keyboard)

        assert rate_buttons == calc_buttons == 8

    def test_callback_data_parsing_roundtrip(self):
        """Test callback data creation and parsing roundtrip."""
        keyboard = CurrencyKeyboard()

        # Test all default currency pairs
        for base, quote in keyboard._currency_pairs:
            # Create callback data
            callback_data = keyboard._create_callback_data(base, quote)

            # Parse it back
            parsed = CurrencyKeyboard.parse_currency_callback(callback_data)

            assert parsed is not None
            assert parsed[0] == "currency"
            assert parsed[1] == base
            assert parsed[2] == quote

    def test_keyboard_layout_mobile_optimization(self):
        """Test keyboard layout is optimized for mobile."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_rate_selection_keyboard()

        # Check 2-column layout (mobile optimization)
        for row in markup.inline_keyboard:
            assert len(row) <= 2, "Row has more than 2 buttons"

        # Should have 4 rows (8 buttons ÷ 2 columns)
        assert len(markup.inline_keyboard) == 4

    def test_emoji_display_consistency(self):
        """Test emoji display consistency across keyboards."""
        keyboard = CurrencyKeyboard()

        rate_markup = keyboard.create_rate_selection_keyboard()

        # Check that all buttons have proper emoji formatting
        for row in rate_markup.inline_keyboard:
            for button in row:
                # Should contain arrow and at least one emoji
                assert "→" in button.text
                # Should have at least one emoji character
                has_emoji = any(ord(char) > 127 for char in button.text)
                assert has_emoji, f"Button text missing emoji: {button.text}"

    def test_admin_keyboard_special_features(self):
        """Test admin keyboard special management features."""
        keyboard = CurrencyKeyboard()
        markup = keyboard.create_admin_currency_keyboard()

        # Should have management buttons
        management_buttons = []
        for row in markup.inline_keyboard:
            for button in row:
                if button.callback_data.startswith("admin:"):
                    management_buttons.append(button)

        # Should have at least add_pair and refresh_pairs
        callback_data_list = [btn.callback_data for btn in management_buttons]
        assert "admin:add_pair" in callback_data_list
        assert "admin:refresh_pairs" in callback_data_list

    def test_manager_keyboard_integration(self):
        """Test manager keyboard integration with other keyboards."""
        keyboard = CurrencyKeyboard()

        rate_markup = keyboard.create_rate_selection_keyboard()
        manager_markup = keyboard.create_manager_selection_keyboard()

        # Both should have same number of currency buttons
        rate_buttons = sum(len(row) for row in rate_markup.inline_keyboard)
        manager_buttons = sum(len(row) for row in manager_markup.inline_keyboard)

        assert rate_buttons == manager_buttons == 8

    def test_manager_callback_parsing_roundtrip(self):
        """Test manager callback data creation and parsing roundtrip."""
        keyboard = CurrencyKeyboard()

        # Test all default currency pairs
        for base, quote in keyboard._currency_pairs:
            # Create manager callback data
            callback_data = f"manager:{base}:{quote}"

            # Parse it back
            parsed = CurrencyKeyboard.parse_currency_callback(callback_data)

            assert parsed is not None
            assert parsed[0] == "manager"
            assert parsed[1] == base
            assert parsed[2] == quote
