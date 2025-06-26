#!/usr/bin/env python3
"""
Crypto Bot - Main Entry Point

Telegram bot for real-time currency exchange rates with Rapira API integration.
This is a placeholder main entry point until the core services are implemented.
"""

import sys
from pathlib import Path


def main() -> None:
    """Main application entry point."""
    print("🚀 Crypto Bot - Technology Validation Complete!")
    print("📋 Status: Foundation setup in progress...")
    print("🔧 Next: Implementing configuration models and core services")
    print("💡 Run tests: python -m pytest tests/unit/validation/")

    # Add src directory to Python path for future imports
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    print(f"✅ Python path configured: {src_path}")


if __name__ == "__main__":
    main()
