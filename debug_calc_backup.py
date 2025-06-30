#!/usr/bin/env python3
"""Debug script to test calc functionality."""

import asyncio
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from config.settings import get_settings
from bot.handlers.calc_handler import get_calc_service


async def test_rate_fetch():
    """Test rate fetching for debugging."""
    print("🔍 Отладка получения курса...")

    settings = get_settings()
    print(f"📋 Настройки API: {settings.rapira_api.base_url}")
    print(f"🔑 API ключ настроен: {'Да' if settings.rapira_api.api_key else 'Нет'}")

    calc_service = get_calc_service(settings)

    # Test different pairs
    test_pairs = [
        ("USDT", "RUB"),
        ("BTC", "USDT"),
        ("ETH", "USDT"),
        ("RUB", "USDT"),
    ]

    for base, quote in test_pairs:
        print(f"\n🧪 Тестирую пару {base}/{quote}...")
        try:
            rate_data = await calc_service.get_rate_for_pair(base, quote)
            if rate_data:
                print(f"✅ Курс найден: {rate_data.close}")
                print(f"📊 Данные: {rate_data.symbol}")
                print(f"📈 Ask: {rate_data.ask_price}, Bid: {rate_data.bid_price}")
            else:
                print("❌ Курс не найден")
        except Exception as e:
            print(f"💥 Ошибка: {e}")

    await calc_service.cleanup()


if __name__ == "__main__":
    asyncio.run(test_rate_fetch())
