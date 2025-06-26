.PHONY: help install test run docker-build docker-run clean

# Default target
help:
	@echo "🚀 Crypto Bot - Simple MVP Commands"
	@echo ""
	@echo "Essential commands:"
	@echo "  install      - Install dependencies"
	@echo "  test         - Run tests"
	@echo "  run          - Run the bot"
	@echo "  clean        - Clean cache files"
	@echo ""
	@echo "Docker commands:"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run with Docker"
	@echo "  docker-stop  - Stop containers"
	@echo ""
	@echo "Optional (add later):"
	@echo "  format       - Format code with Black"

# Essential commands
install:
	pip install -e ".[test]"

install-dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

run:
	python main.py

# Optional formatting (manual)
format:
	black src/ tests/ --line-length=88

# Docker commands
docker-build:
	docker build --target production -t crypto-bot:latest .

docker-run:
	docker-compose up -d crypto-bot redis

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f crypto-bot

# Cleaning
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf htmlcov/ build/ dist/

# MVP Development workflow
mvp-setup: install
	@echo "✅ MVP environment ready!"
	@echo "👉 Run 'make test' to verify setup"
	@echo "👉 Run 'make run' to start development"
