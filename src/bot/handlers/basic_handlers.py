"""Basic command handlers for the crypto bot.

This module provides handlers for essential commands like /start and /help.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import Settings


def create_basic_router() -> Router:
    """Create and configure basic handlers router.

    Returns:
        Configured router with basic handlers
    """
    router = Router(name="basic_handlers")

    @router.message(Command("start"))
    async def cmd_start(message: Message, settings: Settings) -> None:
        """Handle /start command - welcome message."""
        user_name = message.from_user.first_name if message.from_user else "друг"

        welcome_text = f"""
🚀 <b>Добро пожаловать в Crypto Bot, {user_name}!</b>

💱 Я помогу вам получать актуальные курсы валют и рассчитывать суммы для обмена.

<b>Доступные команды:</b>
/rate - 💱 Посмотреть курс валютной пары
/calc - 🧮 Рассчитать сумму обмена
/help - ❓ Показать эту справку

<b>Поддерживаемые валютные пары:</b>
{_format_supported_pairs(settings)}

Выберите команду из меню или введите её вручную! 👆
        """.strip()

        await message.answer(welcome_text)

    @router.message(Command("help"))
    async def cmd_help(message: Message, settings: Settings) -> None:
        """Handle /help command - show help information."""
        help_text = f"""
❓ <b>Справка по командам</b>

<b>💱 /rate</b> - Получить курс валютной пары
Показывает текущий курс с учетом наценки. Выберите валютную пару из
предложенных вариантов.

<b>🧮 /calc</b> - Рассчитать сумму обмена
Поможет рассчитать итоговую сумму для обмена с учетом наценки и комиссий.

<b>🚀 /start</b> - Начать работу с ботом
Показывает приветственное сообщение и основную информацию.

<b>❓ /help</b> - Показать эту справку
Подробная информация о всех доступных командах.

<b>Поддерживаемые валюты:</b>
{_format_supported_pairs(settings)}

<b>ℹ️ Дополнительная информация:</b>
• Курсы обновляются в реальном времени
• Наценка применяется автоматически
• Все расчеты производятся с высокой точностью

Если у вас есть вопросы, обратитесь к администратору.
        """.strip()

        await message.answer(help_text)

    return router


def _format_supported_pairs(settings: Settings) -> str:
    """Format supported currency pairs for display."""
    pairs = settings.supported_pairs_list
    if not pairs:
        return "Валютные пары не настроены"

    # Group pairs by base currency for better readability
    grouped = {}
    for pair in pairs:
        if "/" in pair:
            base, quote = pair.split("/")
            if base not in grouped:
                grouped[base] = []
            grouped[base].append(quote)

    if not grouped:
        return "Валютные пары не настроены"

    formatted_lines = []
    for base, quotes in grouped.items():
        quotes_str = ", ".join(quotes)
        formatted_lines.append(f"• <b>{base}</b>: {quotes_str}")

    return "\n".join(formatted_lines)
