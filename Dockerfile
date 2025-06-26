# Multi-stage build for Crypto Bot
FROM python:3.11-slim as builder

# Set environment variables for build optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy pyproject.toml for dependency installation
COPY pyproject.toml ./

# Install Python dependencies from pyproject.toml
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .[test] && \
    pip install --no-deps .

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r -g 1000 botuser && \
    useradd -r -u 1000 -g botuser -d /app -s /bin/bash botuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create application directory and set ownership
WORKDIR /app
RUN chown -R botuser:botuser /app

# Copy application code with proper ownership
COPY --chown=botuser:botuser src/ ./src/
COPY --chown=botuser:botuser main.py ./
COPY --chown=botuser:botuser pyproject.toml ./

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data && \
    chown -R botuser:botuser /app/logs /app/data

# Switch to non-root user
USER botuser

# Health check with proper timeout and retries
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import sys; import asyncio; from src.config.settings import Settings; settings = Settings(); sys.exit(0 if settings else 1)" || exit 1

# Expose port for webhook mode (optional)
EXPOSE 8080

# Use exec form for proper signal handling
CMD ["python", "-m", "src.main"]

# Development stage (for local development)
FROM builder as development

# Install development dependencies
RUN pip install -e .[dev]

# Copy pre-commit hooks and development tools
COPY --chown=botuser:botuser .pre-commit-config.yaml* ./
COPY --chown=botuser:botuser Makefile* ./

# Set development environment
ENV ENVIRONMENT=development \
    LOG_LEVEL=DEBUG

# Switch to non-root user
USER botuser

# Development command with auto-reload
CMD ["python", "-m", "src.main", "--reload"]
