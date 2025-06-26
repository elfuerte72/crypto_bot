.PHONY: help install install-dev test test-cov lint format type-check pre-commit clean run docker-build docker-run docker-dev docker-monitoring

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
	@echo ""
	@echo "Docker commands:"
	@echo "  docker-build      - Build production Docker image"
	@echo "  docker-build-dev  - Build development Docker image"
	@echo "  docker-run        - Run production containers"
	@echo "  docker-dev        - Run development containers"
	@echo "  docker-monitoring - Run with monitoring stack"
	@echo "  docker-stop       - Stop all containers"
	@echo "  docker-clean      - Clean Docker resources"
	@echo "  docker-logs       - Show container logs"

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

# Docker Production
docker-build:
	docker build --target production -t crypto-bot:latest .
	@echo "Production image built: crypto-bot:latest"

docker-build-dev:
	docker build --target development -t crypto-bot:dev .
	@echo "Development image built: crypto-bot:dev"

docker-run:
	docker-compose up -d crypto-bot redis
	@echo "Production containers started"
	@echo "Bot: http://localhost:8080"
	@echo "Redis: localhost:6379"

docker-dev:
	docker-compose --profile dev up -d
	@echo "Development containers started"
	@echo "Bot: http://localhost:8080"
	@echo "Redis: localhost:6379"

docker-monitoring:
	docker-compose --profile monitoring up -d
	@echo "Monitoring stack started"
	@echo "Grafana: http://localhost:3000 (admin/admin123)"
	@echo "Prometheus: http://localhost:9090"

docker-debug:
	docker-compose --profile debug up -d
	@echo "Debug containers started"
	@echo "Redis Commander: http://localhost:8081"

docker-stop:
	docker-compose down
	@echo "All containers stopped"

docker-restart:
	docker-compose restart crypto-bot
	@echo "Bot container restarted"

docker-logs:
	docker-compose logs -f crypto-bot

docker-logs-all:
	docker-compose logs -f

docker-shell:
	docker-compose exec crypto-bot /bin/bash

docker-redis-cli:
	docker-compose exec redis redis-cli

docker-clean:
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f
	@echo "Docker resources cleaned"

docker-rebuild:
	docker-compose down
	docker build --no-cache --target production -t crypto-bot:latest .
	docker-compose up -d
	@echo "Containers rebuilt and restarted"

# Docker health checks
docker-health:
	@echo "=== Container Health Status ==="
	docker-compose ps
	@echo ""
	@echo "=== Bot Health Check ==="
	docker-compose exec crypto-bot python -c "from src.config.settings import Settings; print('✅ Config OK' if Settings() else '❌ Config Failed')" || echo "❌ Bot container not running"
	@echo ""
	@echo "=== Redis Health Check ==="
	docker-compose exec redis redis-cli ping || echo "❌ Redis container not running"

# Development workflow
dev-setup: install-dev pre-commit-install
	@echo "Development environment setup complete!"

dev-check: format lint type-check test
	@echo "All checks passed!"

# Docker development workflow
docker-dev-setup: docker-build-dev
	@echo "Docker development environment ready!"

docker-test:
	docker build --target development -t crypto-bot:test .
	docker run --rm crypto-bot:test pytest tests/ -v

# CI/CD helpers
ci-test:
	pytest tests/ -v --cov=src --cov-report=xml --cov-fail-under=80

ci-quality:
	ruff check src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/
	mypy src/

ci-docker:
	docker build --target production -t crypto-bot:ci .
	docker run --rm crypto-bot:ci python -c "from src.config.settings import Settings; Settings()"
