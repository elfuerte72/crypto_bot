#!/usr/bin/env python3
"""Демонстрация работы inline клавиатур для crypto bot.

Этот скрипт показывает, как выглядят созданные клавиатуры.
"""

from src.bot.keyboards.currency_keyboard import (
    CurrencyKeyboard,
    parse_callback,
)


def demo_keyboard_structure(keyboard_name: str, markup):
    """Показать структуру клавиатуры."""
    print(f"\n=== {keyboard_name} ===")
    print(f"Количество рядов: {len(markup.inline_keyboard)}")

    total_buttons = sum(len(row) for row in markup.inline_keyboard)
    print(f"Общее количество кнопок: {total_buttons}")

    print("\nСтруктура клавиатуры:")
    for i, row in enumerate(markup.inline_keyboard):
        print(f"  Ряд {i+1}: {len(row)} кнопок")
        for j, button in enumerate(row):
            print(f"    Кнопка {j+1}: '{button.text}' -> '{button.callback_data}'")


def demo_callback_parsing():
    """Демонстрация парсинга callback данных."""
    print("\n=== ДЕМО ПАРСИНГА CALLBACK ДАННЫХ ===")

    test_callbacks = [
        "currency:RUB:ZAR",
        "currency:USDT:THB",
        "markup:RUB:AED",
        "admin:currency:BTC:USD",
        "invalid_callback",
        "currency:RUB",  # неполные данные
    ]

    for callback in test_callbacks:
        result = parse_callback(callback)
        if result:
            action, base, quote = result
            print(
                f"'{callback}' -> Действие: {action}, Базовая: {base}, Котируемая: {quote}"
            )
        else:
            print(f"'{callback}' -> ОШИБКА ПАРСИНГА")


def main():
    """Главная функция демонстрации."""
    print("🤖 ДЕМОНСТРАЦИЯ INLINE КЛАВИАТУР CRYPTO BOT")
    print("=" * 50)

    # Создаем экземпляр клавиатуры
    keyboard = CurrencyKeyboard()

    # Демонстрируем разные типы клавиатур
    rate_markup = keyboard.create_rate_selection_keyboard()
    demo_keyboard_structure("КЛАВИАТУРА ВЫБОРА КУРСА", rate_markup)

    calc_markup = keyboard.create_calc_selection_keyboard()
    demo_keyboard_structure("КЛАВИАТУРА РАСЧЕТОВ", calc_markup)

    admin_markup = keyboard.create_admin_currency_keyboard()
    demo_keyboard_structure("АДМИНСКАЯ КЛАВИАТУРА", admin_markup)

    markup_markup = keyboard.create_markup_selection_keyboard()
    demo_keyboard_structure("КЛАВИАТУРА НАСТРОЙКИ НАЦЕНКИ", markup_markup)

    # Демонстрируем вспомогательные клавиатуры
    back_markup = CurrencyKeyboard.create_back_keyboard()
    demo_keyboard_structure("КНОПКА НАЗАД", back_markup)

    confirm_markup = CurrencyKeyboard.create_confirm_keyboard()
    demo_keyboard_structure("КЛАВИАТУРА ПОДТВЕРЖДЕНИЯ", confirm_markup)

    # Демонстрируем парсинг callback данных
    demo_callback_parsing()

    # Показываем информацию о валютных парах
    print("\n=== ИНФОРМАЦИЯ О ВАЛЮТНЫХ ПАРАХ ===")
    print(f"Поддерживаемые пары: {len(keyboard._currency_pairs)}")
    for i, (base, quote) in enumerate(keyboard._currency_pairs, 1):
        emoji_base = keyboard.CURRENCY_EMOJIS.get(base, "")
        emoji_quote = keyboard.CURRENCY_EMOJIS.get(quote, "")
        print(f"  {i}. {emoji_base} {base} ↔ {quote} {emoji_quote}")

    print(f"\nВсего направлений обмена: {len(keyboard._currency_pairs) * 2}")

    print("\n✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")


if __name__ == "__main__":
    main()
