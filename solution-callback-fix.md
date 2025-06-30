# 🔧 Решение проблемы с необработанными Callback-кнопками

## 🎯 Проблема
Кнопка "🧮 Рассчитать" не обрабатывалась ботом. В логах появлялось сообщение:
```
Update id=212159511 is not handled. Duration 5 ms
```

## 🔍 Причина
В файле `src/bot/handlers/calc_handler.py` было **два обработчика** для одного и того же `callback_data = "start_calculation"`:

1. **Основной обработчик** (строка 378) - правильно проверял состояние FSM:
```python
@calc_router.callback_query(CalcStates.showing_rate, F.data == "start_calculation")
async def handle_start_calculation(callback: CallbackQuery, state: FSMContext, settings: Settings)
```

2. **Тестовый обработчик** (строка 728) - перехватывал ВСЕ callback без проверки состояния:
```python
@calc_router.callback_query(F.data == "start_calculation")  # БЕЗ проверки состояния!
async def handle_start_calculation_simple(callback: CallbackQuery, state: FSMContext)
```

Второй обработчик перехватывал callback до того, как основной обработчик мог его обработать.

## ✅ Решение
Закомментировал конфликтующий тестовый обработчик:
```python
# Simple test handler for start_calculation - DISABLED to avoid conflict
# @calc_router.callback_query(F.data == "start_calculation")
# async def handle_start_calculation_simple(...):
#     ...
```

## 📊 Результат
После исправления:
- ✅ Кнопка "🧮 Рассчитать" теперь работает корректно
- ✅ FSM состояния переключаются правильно
- ✅ Пользователь может ввести сумму для расчёта
- ✅ Callback обрабатывается основным обработчиком с проверкой состояния

## 💡 Выводы
1. **Всегда проверяйте дублирующие обработчики** - особенно тестовые
2. **Используйте фильтры состояний FSM** для корректной маршрутизации
3. **Удаляйте или комментируйте тестовый код** перед продакшеном
4. **Логирование помогает** быстро найти проблему

## 🚀 Проверка работы
```bash
# Запустить бота
python main.py

# В Telegram:
1. /calc - запустить калькулятор
2. Выбрать валютную пару
3. Нажать "🧮 Рассчитать" - теперь работает!
4. Ввести сумму
5. Получить результат расчёта
```

## 🛠️ Дополнительные улучшения (опционально)

### 1. Очистка неиспользуемых импортов
В файле есть несколько неиспользуемых импортов, которые можно удалить:
- `asyncio`
- `StorageKey`
- Некоторые исключения из `calculation_service`

### 2. Добавление проверки состояния в общий обработчик
Обработчик `handle_unhandled_callback` на строке 738 можно улучшить для лучшей диагностики:
```python
@calc_router.callback_query()
async def handle_unhandled_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle unhandled callback queries for debugging."""
    current_state = await state.get_state()
    logger.warning(
        f"Unhandled callback: data='{callback.data}', "
        f"user={callback.from_user.id}, current_state={current_state}"
    )
    # Можно добавить более информативное сообщение
    if callback.data == "start_calculation" and current_state != CalcStates.showing_rate:
        await callback.answer("❌ Сначала выберите валютную пару", show_alert=True)
    else:
        await callback.answer("❌ Неизвестная команда", show_alert=True)
```
