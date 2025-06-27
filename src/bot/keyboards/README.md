# Inline Keyboards Module

Этот модуль предоставляет систему inline клавиатур для Telegram бота обмена валют.

## Возможности

### ✨ Основные функции
- **Динамическое создание клавиатур** для выбора валютных пар
- **Мобильная оптимизация** с 2-колоночным макетом
- **Эмодзи поддержка** для визуального представления валют
- **Множественные типы клавиатур** для разных сценариев использования
- **Парсинг callback данных** с валидацией
- **Интеграция с настройками** для динамической конфигурации

### 🎯 Поддерживаемые валютные пары
- **RUB** (Российский рубль) 🇷🇺 ↔ ZAR, THB, AED, IDR
- **USDT** (Tether) 💰 ↔ ZAR, THB, AED, IDR
- **Всего**: 8 пар в обоих направлениях (16 комбинаций)

### 📱 Типы клавиатур

#### 1. Клавиатура выбора курса (`create_rate_selection_keyboard`)
Используется для команды `/rate` - показывает все валютные пары для получения курса.

#### 2. Клавиатура расчетов (`create_calc_selection_keyboard`)
Используется для команды `/calc` - показывает валютные пары для расчета суммы.

#### 3. Админская клавиатура (`create_admin_currency_keyboard`)
Специальная клавиатура для администраторов с дополнительными опциями управления.

#### 4. Клавиатура настройки наценки (`create_markup_selection_keyboard`)
Для настройки процента наценки по валютным парам.

#### 5. Вспомогательные клавиатуры
- **Кнопка "Назад"** (`create_back_keyboard`)
- **Подтверждение** (`create_confirm_keyboard`)

## Использование

### Быстрое начало

```python
from src.bot.keyboards.currency_keyboard import get_rate_keyboard

# Создание клавиатуры для выбора курса
markup = get_rate_keyboard()

# Отправка сообщения с клавиатурой
await message.answer("Выберите валютную пару:", reply_markup=markup)
```

### Расширенное использование

```python
from src.bot.keyboards.currency_keyboard import CurrencyKeyboard
from src.config.models import Settings

# Создание с настройками
settings = Settings()
keyboard = CurrencyKeyboard(settings)

# Различные типы клавиатур
rate_markup = keyboard.create_rate_selection_keyboard()
calc_markup = keyboard.create_calc_selection_keyboard()
admin_markup = keyboard.create_admin_currency_keyboard()
```

### Обработка callback данных

```python
from src.bot.keyboards.currency_keyboard import parse_callback

@router.callback_query(F.data.startswith("currency:"))
async def handle_currency_selection(callback: CallbackQuery):
    result = parse_callback(callback.data)
    if result:
        action, base_currency, quote_currency = result
        # Обработка выбора валютной пары
        await callback.answer(f"Выбрана пара: {base_currency}/{quote_currency}")
```

## Структура callback данных

### Формат данных
- **Выбор валюты**: `currency:BASE:QUOTE` (например, `currency:RUB:ZAR`)
- **Настройка наценки**: `markup:BASE:QUOTE` (например, `markup:USDT:THB`)
- **Админские действия**: `admin:ACTION:PARAMS` (например, `admin:add_pair`)

### Парсинг callback данных

```python
# Валидные форматы
"currency:RUB:ZAR" → ("currency", "RUB", "ZAR")
"markup:USDT:THB" → ("markup", "USDT", "THB")
"admin:currency:BTC:USD" → ("admin", "currency", "BTC")

# Невалидные форматы возвращают None
"invalid_data" → None
"currency:RUB" → None  # недостаточно частей
```

## Конфигурация

### Валютные эмодзи

```python
CURRENCY_EMOJIS = {
    "RUB": "🇷🇺",   # Российский рубль
    "USDT": "💰",    # Tether
    "ZAR": "🇿🇦",    # Южноафриканский рэнд
    "THB": "🇹🇭",    # Тайский бат
    "AED": "🇦🇪",    # Дирхам ОАЭ
    "IDR": "🇮🇩",    # Индонезийская рупия
}
```

### Валютные пары по умолчанию

```python
DEFAULT_CURRENCY_PAIRS = [
    ("RUB", "ZAR"),   # RUB → ZAR, ZAR → RUB
    ("RUB", "THB"),   # RUB → THB, THB → RUB
    ("RUB", "AED"),   # RUB → AED, AED → RUB
    ("RUB", "IDR"),   # RUB → IDR, IDR → RUB
    ("USDT", "ZAR"),  # USDT → ZAR, ZAR → USDT
    ("USDT", "THB"),  # USDT → THB, THB → USDT
    ("USDT", "AED"),  # USDT → AED, AED → USDT
    ("USDT", "IDR"),  # USDT → IDR, IDR → USDT
]
```

## API Reference

### CurrencyKeyboard класс

#### Методы

- `__init__(settings: Optional[Settings] = None)` - Инициализация
- `create_rate_selection_keyboard()` - Клавиатура выбора курса
- `create_calc_selection_keyboard()` - Клавиатура расчетов
- `create_admin_currency_keyboard()` - Админская клавиатура
- `create_markup_selection_keyboard()` - Клавиатура настройки наценки

#### Статические методы

- `parse_currency_callback(callback_data: str)` - Парсинг callback данных
- `create_back_keyboard(callback_data: str = "back")` - Кнопка "Назад"
- `create_confirm_keyboard(confirm_data: str = "confirm", cancel_data: str = "cancel")` - Подтверждение

### Convenience функции

- `get_rate_keyboard(settings: Optional[Settings] = None)` - Быстрое создание клавиатуры курса
- `get_calc_keyboard(settings: Optional[Settings] = None)` - Быстрое создание клавиатуры расчетов
- `get_admin_keyboard(settings: Optional[Settings] = None)` - Быстрое создание админской клавиатуры
- `parse_callback(callback_data: str)` - Быстрый парсинг callback данных

## Тестирование

Модуль полностью покрыт unit тестами:

```bash
# Запуск тестов
python -m pytest tests/unit/bot/keyboards/test_currency_keyboard.py -v

# Демонстрация функциональности
python tests/manual/demo_keyboards.py
```

### Покрытие тестами
- ✅ **29 unit тестов** покрывают все функции
- ✅ Тестирование различных типов клавиатур
- ✅ Валидация callback данных
- ✅ Интеграционные тесты
- ✅ Тестирование мобильной оптимизации
- ✅ Проверка консистентности эмодзи

## Совместимость

- **Python**: 3.11+
- **Aiogram**: 3.x
- **Pydantic**: 2.x

## Лицензия

Часть проекта Crypto Bot. Все права защищены.
