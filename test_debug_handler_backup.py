#!/usr/bin/env python3
"""Simple test to debug calc handler."""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from dotenv import load_dotenv

load_dotenv(override=True)

from bot.handlers.calc_handler import calc_router


def test_handlers():
    """Test calc handler registration."""
    print("🔍 Отладка обработчиков calc_router...")

    # Get all handlers
    handlers = []
    for observer in calc_router.observers.values():
        for handler in observer:
            handlers.append(handler)

    print(f"📊 Всего обработчиков: {len(handlers)}")

    for i, handler in enumerate(handlers):
        print(f"  {i+1}. {handler.callback.__name__}")
        if hasattr(handler, "filters"):
            print(f"     Фильтры: {handler.filters}")
        print()


if __name__ == "__main__":
    test_handlers()
