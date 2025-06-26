.PHONY: help install install-dev test test-cov lint format type-check pre-commit clean run docker-build docker-run

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  lint         - Run linting (ruff)"
	@echo "  format       - Format code (black + isort)"
	@echo "  type-check   - Run type checking (mypy)"
	@echo "  pre-commit   - Run pre-commit hooks"
	@echo "  clean        - Clean cache and build files"
	@echo "  run          - Run the bot"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# Code quality
lint:
	ruff check src/ tests/

lint-fix:
	ruff check src/ tests/ --fix

format:
	black src/ tests/
	isort src/ tests/

type-check:
	mypy src/

# Pre-commit
pre-commit:
	pre-commit run --all-files

pre-commit-install:
	pre-commit install

# Cleaning
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/

# Running
run:
	python main.py

run-dev:
	python main.py --debug

# Docker
docker-build:
	docker build -t crypto-bot .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Development workflow
dev-setup: install-dev pre-commit-install
	@echo "Development environment setup complete!"

dev-check: format lint type-check test
	@echo "All checks passed!"

# CI/CD helpers
ci-test:
	pytest tests/ -v --cov=src --cov-report=xml --cov-fail-under=80

ci-quality:
	ruff check src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/
	mypy src/
