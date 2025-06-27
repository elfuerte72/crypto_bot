"""Currency selection inline keyboards for the crypto bot.

This module provides inline keyboards for currency pair selection with optimized
layout for mobile devices and clear user experience.
"""

from __future__ import annotations

from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...config.models import Settings


class CurrencyKeyboard:
    """Factory class for creating currency selection inline keyboards."""

    # Supported currency pairs based on project requirements
    # 8 currency pairs: RUB, USDT vs ZAR, THB, AED, IDR (16 combinations total)
    DEFAULT_CURRENCY_PAIRS = [
        ("RUB", "ZAR"),  # Russian Ruble to South African Rand
        ("RUB", "THB"),  # Russian Ruble to Thai Baht
        ("RUB", "AED"),  # Russian Ruble to UAE Dirham
        ("RUB", "IDR"),  # Russian Ruble to Indonesian Rupiah
        ("USDT", "ZAR"),  # Tether to South African Rand
        ("USDT", "THB"),  # Tether to Thai Baht
        ("USDT", "AED"),  # Tether to UAE Dirham
        ("USDT", "IDR"),  # Tether to Indonesian Rupiah
    ]

    # Emoji mapping for better visual representation
    CURRENCY_EMOJIS = {
        "RUB": "🇷🇺",
        "USDT": "💰",
        "ZAR": "🇿🇦",
        "THB": "🇹🇭",
        "AED": "🇦🇪",
        "IDR": "🇮🇩",
    }

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize currency keyboard factory.

        Args:
            settings: Application settings containing currency pair configurations
        """
        self.settings = settings
        self._currency_pairs = self._get_currency_pairs()

    def _get_currency_pairs(self) -> List[tuple[str, str]]:
        """Get currency pairs from settings or use defaults.

        Returns:
            List of currency pair tuples (base, quote)
        """
        if self.settings and self.settings.currency_pairs:
            pairs = []
            for pair_config in self.settings.get_active_currency_pairs():
                pairs.append((pair_config.base, pair_config.quote))
            return pairs

        return self.DEFAULT_CURRENCY_PAIRS

    def _format_currency_button_text(self, base: str, quote: str) -> str:
        """Format currency pair button text with emojis.

        Args:
            base: Base currency code
            quote: Quote currency code

        Returns:
            Formatted button text with emojis
        """
        base_emoji = self.CURRENCY_EMOJIS.get(base, "")
        quote_emoji = self.CURRENCY_EMOJIS.get(quote, "")

        return f"{base_emoji} {base} → {quote} {quote_emoji}"

    def _create_callback_data(self, base: str, quote: str) -> str:
        """Create callback data for currency pair selection.

        Args:
            base: Base currency code
            quote: Quote currency code

        Returns:
            Callback data string
        """
        return f"currency:{base}:{quote}"

    def create_rate_selection_keyboard(self) -> InlineKeyboardMarkup:
        """Create keyboard for rate command currency selection.

        Returns:
            InlineKeyboardMarkup with currency pair buttons
        """
        builder = InlineKeyboardBuilder()

        # Add all currency pairs in both directions (16 total)
        for base, quote in self._currency_pairs:
            # Forward direction (e.g., RUB → ZAR)
            builder.button(
                text=self._format_currency_button_text(base, quote),
                callback_data=self._create_callback_data(base, quote),
            )

            # Reverse direction (e.g., ZAR → RUB)
            builder.button(
                text=self._format_currency_button_text(quote, base),
                callback_data=self._create_callback_data(quote, base),
            )

        # Adjust layout: 2 columns for mobile optimization
        # This creates a clean 2-column layout with 8 rows
        builder.adjust(2)

        return builder.as_markup()

    def create_calc_selection_keyboard(self) -> InlineKeyboardMarkup:
        """Create keyboard for calc command currency selection.

        Returns:
            InlineKeyboardMarkup with currency pair buttons
        """
        # Same layout as rate selection for consistency
        return self.create_rate_selection_keyboard()

    def create_admin_currency_keyboard(self) -> InlineKeyboardMarkup:
        """Create keyboard for admin currency management.

        Returns:
            InlineKeyboardMarkup with currency management options
        """
        builder = InlineKeyboardBuilder()

        # Add currency pairs for admin management
        for base, quote in self._currency_pairs:
            # Only forward direction for admin management
            builder.button(
                text=f"{base}/{quote}", callback_data=f"admin:currency:{base}:{quote}"
            )

        # Add management options
        builder.row(
            InlineKeyboardButton(
                text="➕ Добавить пару", callback_data="admin:add_pair"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить", callback_data="admin:refresh_pairs"
            ),
        )

        # Adjust layout: 2 columns for pairs, full width for management buttons
        builder.adjust(2, 2)

        return builder.as_markup()

    def create_markup_selection_keyboard(self) -> InlineKeyboardMarkup:
        """Create keyboard for markup rate selection.

        Returns:
            InlineKeyboardMarkup with currency pairs for markup management
        """
        builder = InlineKeyboardBuilder()

        for base, quote in self._currency_pairs:
            # Show current markup rate if available
            markup_rate = "2.5%"  # Default
            if self.settings:
                pair_config = self.settings.get_currency_pair(f"{base}/{quote}")
                if pair_config:
                    markup_rate = f"{pair_config.markup_rate}%"

            builder.button(
                text=f"{base}/{quote} ({markup_rate})",
                callback_data=f"markup:{base}:{quote}",
            )

        # 2-column layout
        builder.adjust(2)

        return builder.as_markup()

    @staticmethod
    def parse_currency_callback(callback_data: str) -> tuple[str, str, str] | None:
        """Parse currency callback data.

        Args:
            callback_data: Callback data string

        Returns:
            Tuple of (action, base_currency, quote_currency) or None if invalid
        """
        try:
            parts = callback_data.split(":")
            if len(parts) >= 3:
                action = parts[0]
                base = parts[1]
                quote = parts[2]
                return action, base, quote
        except (ValueError, IndexError):
            pass

        return None

    @staticmethod
    def create_back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
        """Create simple back button keyboard.

        Args:
            callback_data: Callback data for back button

        Returns:
            InlineKeyboardMarkup with back button
        """
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data=callback_data)
        return builder.as_markup()

    @staticmethod
    def create_confirm_keyboard(
        confirm_data: str = "confirm", cancel_data: str = "cancel"
    ) -> InlineKeyboardMarkup:
        """Create confirmation keyboard with confirm/cancel buttons.

        Args:
            confirm_data: Callback data for confirm button
            cancel_data: Callback data for cancel button

        Returns:
            InlineKeyboardMarkup with confirm/cancel buttons
        """
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data),
        )
        return builder.as_markup()


# Convenience functions for quick keyboard creation
def get_rate_keyboard(settings: Optional[Settings] = None) -> InlineKeyboardMarkup:
    """Get rate selection keyboard.

    Args:
        settings: Application settings

    Returns:
        InlineKeyboardMarkup for rate selection
    """
    keyboard = CurrencyKeyboard(settings)
    return keyboard.create_rate_selection_keyboard()


def get_calc_keyboard(settings: Optional[Settings] = None) -> InlineKeyboardMarkup:
    """Get calculation selection keyboard.

    Args:
        settings: Application settings

    Returns:
        InlineKeyboardMarkup for calculation selection
    """
    keyboard = CurrencyKeyboard(settings)
    return keyboard.create_calc_selection_keyboard()


def get_admin_keyboard(settings: Optional[Settings] = None) -> InlineKeyboardMarkup:
    """Get admin currency management keyboard.

    Args:
        settings: Application settings

    Returns:
        InlineKeyboardMarkup for admin management
    """
    keyboard = CurrencyKeyboard(settings)
    return keyboard.create_admin_currency_keyboard()


def parse_callback(callback_data: str) -> tuple[str, str, str] | None:
    """Parse currency callback data.

    Args:
        callback_data: Callback data string

    Returns:
        Tuple of (action, base_currency, quote_currency) or None if invalid
    """
    return CurrencyKeyboard.parse_currency_callback(callback_data)
