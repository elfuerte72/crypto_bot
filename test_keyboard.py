#!/usr/bin/env python3
"""
Простой тест для проверки кнопки "Рассчитать"
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from config.settings import get_settings

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create bot and dispatcher
settings = get_settings()
bot = Bot(token=settings.telegram.token)
dp = Dispatcher()


@dp.message(Command("test"))
async def test_keyboard(message: Message):
    """Тестовая команда для проверки клавиатуры"""

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🧮 Рассчитать", callback_data="start_calculation")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_pair_selection")
    )

    keyboard = builder.as_markup()

    await message.answer(
        "🧮 <b>Тестовая клавиатура</b>\n\n" "Нажмите кнопку 'Рассчитать' для проверки:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    logger.info(f"Keyboard sent to user {message.from_user.id}")


@dp.callback_query(F.data == "start_calculation")
async def handle_test_calculation(callback: CallbackQuery):
    """Обработчик кнопки 'Рассчитать'"""
    logger.info(f"🎯 КНОПКА РАССЧИТАТЬ НАЖАТА! User: {callback.from_user.id}")

    await callback.answer("✅ Кнопка работает!", show_alert=True)

    await callback.message.edit_text(
        "✅ <b>Успех!</b>\n\n" "Кнопка 'Рассчитать' работает корректно!",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "back_to_pair_selection")
async def handle_test_back(callback: CallbackQuery):
    """Обработчик кнопки 'Назад'"""
    logger.info(f"⬅️ КНОПКА НАЗАД НАЖАТА! User: {callback.from_user.id}")

    await callback.answer("Назад", show_alert=False)

    await callback.message.edit_text(
        "⬅️ <b>Назад</b>\n\n" "Кнопка 'Назад' тоже работает!", parse_mode="HTML"
    )


@dp.callback_query()
async def handle_unhandled_callback(callback: CallbackQuery):
    """Обработчик необработанных callback'ов"""
    logger.warning(
        f"❌ Необработанный callback: {callback.data}, user: {callback.from_user.id}"
    )
    await callback.answer("❌ Неизвестная команда", show_alert=True)


async def main():
    """Основная функция"""
    logger.info("🚀 Запуск тестового бота...")

    try:
        # Проверяем подключение
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот подключен: @{bot_info.username}")

        # Запускаем polling
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
