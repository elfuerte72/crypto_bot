# Crypto Bot

Telegram бот для обмена криптовалют с интеграцией Rapira API.

## Возможности

- 🔄 Получение актуальных курсов валют в реальном времени
- 💰 Расчет суммы обмена с настраиваемой наценкой
- 📊 Поддержка 8 валютных пар в обе стороны (16 комбинаций)
- 🚀 Кеширование для быстрого отклика
- 📱 Удобный интерфейс с inline-клавиатурой
- 👥 Уведомления менеджеров о транзакциях
- ⚙️ Административные команды для настройки

## Поддерживаемые валютные пары

- USD/RUB ↔ RUB/USD
- EUR/RUB ↔ RUB/EUR
- USD/EUR ↔ EUR/USD
- BTC/USD ↔ USD/BTC
- ETH/USD ↔ USD/ETH
- USDT/RUB ↔ RUB/USDT
- BTC/RUB ↔ RUB/BTC
- ETH/RUB ↔ RUB/ETH

## Установка и запуск

### Требования

- Python 3.11+
- Redis
- Telegram Bot Token
- Rapira API Key

### Быстрый старт

1. **Клонирование и настройка окружения:**
```bash
git clone <repository-url>
cd crypto_bot
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\\Scripts\\activate  # Windows

# Установка production зависимостей
pip install -e .

# Или для разработки (включает dev инструменты)
pip install -e ".[dev]"
```

2. **Настройка конфигурации:**
```bash
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

3. **Запуск Redis:**
```bash
redis-server
```

4. **Запуск бота:**
```bash
python main.py
```

## Конфигурация

Основные настройки в файле `.env`:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_USER_ID=your_admin_user_id_here

# Rapira API
RAPIRA_API_URL=https://api.rapira.exchange
RAPIRA_API_KEY=your_rapira_api_key_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Настройки
DEFAULT_MARKUP_RATE=2.5
RATE_CACHE_TTL=300
```

## Команды бота

### Пользовательские команды
- `/start` - Приветствие и инструкции
- `/rate` - Получить текущий курс валютной пары
- `/calc` - Рассчитать сумму обмена
- `/help` - Справка по командам

### Административные команды
- `/set_markup <pair> <rate>` - Установить наценку для валютной пары
- `/set_manager <pair> <user_id>` - Назначить менеджера для валютной пары
- `/stats` - Статистика использования

## Архитектура

```
src/
├── bot/                 # Telegram bot handlers
├── services/           # Business logic services
│   ├── rate_service.py    # Rapira API integration
│   ├── cache_service.py   # Redis caching
│   ├── calculation_service.py  # Exchange calculations
│   └── notification_service.py # Manager notifications
├── models/             # Data models
├── config/             # Configuration management
└── main.py            # Application entry point
```

## Разработка

### Настройка среды разработки

```bash
# Установка зависимостей разработки
pip install -e ".[dev]"

# Настройка pre-commit hooks
pre-commit install

# Или используйте Makefile команды:
make dev-setup  # Полная настройка
make format     # Форматирование кода
make lint       # Линтинг
make type-check # Проверка типов
make test       # Тестирование
make dev-check  # Все проверки
```

### Тестирование

```bash
# Запуск всех тестов
pytest

# Тесты с покрытием
pytest --cov=src

# Только unit тесты
pytest -m unit

# Только integration тесты
pytest -m integration
```

## Docker

```bash
# Сборка образа
docker build -t crypto-bot .

# Запуск с docker-compose
docker-compose up -d
```

## Мониторинг

Бот поддерживает структурированное логирование и метрики:

- Логи в формате JSON для production
- Метрики производительности
- Мониторинг состояния внешних API
- Алерты при критических ошибках

## Лицензия

MIT License

## Поддержка

Для вопросов и поддержки создайте issue в репозитории.# crypto_bot
