#!/usr/bin/env python3
"""Debug script to test live calc flow with detailed logging."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from config.settings import get_settings
from bot.handlers.calc_handler import handle_pair_selection
from bot.states.calc_states import CalcStates, CalcData
from bot.keyboards.currency_keyboard import CurrencyKeyboard


async def test_pair_selection_flow():
    """Test the pair selection flow step by step."""
    print("🔍 Отладка потока выбора пары...")

    # Create mock objects
    callback = MagicMock()
    callback.data = "currency:USDT:RUB"
    callback.message = AsyncMock()
    callback.answer = AsyncMock()

    state = AsyncMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    settings = get_settings()

    print(f"📋 Тестируем с парой: {callback.data}")
    print(f"🔧 Настройки API: {settings.rapira_api.base_url}")

    try:
        # Call the handler
        await handle_pair_selection(callback, state, settings)

        print("✅ Обработчик выполнился без ошибок")

        # Check what was called
        print(f"📞 state.update_data вызван: {state.update_data.called}")
        print(f"📞 state.set_state вызван: {state.set_state.called}")
        print(
            f"📞 callback.message.edit_text вызван: {callback.message.edit_text.called}"
        )
        print(f"📞 callback.answer вызван: {callback.answer.called}")

        # Check if set_state was called with showing_rate
        if state.set_state.called:
            args = state.set_state.call_args
            print(f"🎯 set_state вызван с: {args}")

        # Check message content
        if callback.message.edit_text.called:
            args = callback.message.edit_text.call_args
            print(f"💬 Сообщение: {args[0][0][:100]}...")

            # Check if keyboard was passed
            if len(args[1]) > 0 and "reply_markup" in args[1]:
                keyboard = args[1]["reply_markup"]
                print(f"⌨️ Клавиатура передана: {keyboard is not None}")
                if keyboard:
                    print(f"🔘 Кнопки: {keyboard.inline_keyboard}")

    except Exception as e:
        print(f"💥 Ошибка в обработчике: {e}")
        import traceback

        traceback.print_exc()


async def test_keyboard_creation():
    """Test keyboard creation."""
    print("\n🔍 Тестируем создание клавиатуры...")

    try:
        keyboard = CurrencyKeyboard.create_calculate_keyboard()
        print("✅ Клавиатура создана успешно")
        print(f"🔘 Количество рядов: {len(keyboard.inline_keyboard)}")

        for i, row in enumerate(keyboard.inline_keyboard):
            print(f"  Ряд {i+1}:")
            for j, button in enumerate(row):
                print(f"    Кнопка {j+1}: '{button.text}' -> '{button.callback_data}'")

    except Exception as e:
        print(f"💥 Ошибка создания клавиатуры: {e}")


if __name__ == "__main__":

    async def main():
        await test_keyboard_creation()
        await test_pair_selection_flow()

    asyncio.run(main())
