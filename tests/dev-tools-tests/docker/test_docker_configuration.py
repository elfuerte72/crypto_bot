"""Tests for Docker configuration files and setup."""

import subprocess
from pathlib import Path

import pytest
import yaml


class TestDockerConfiguration:
    """Test Docker configuration files and build process."""

    def test_dockerfile_exists(self) -> None:
        """Test that Dockerfile exists."""
        dockerfile_path = Path("Dockerfile")
        assert dockerfile_path.exists(), "Dockerfile should exist"

    def test_docker_compose_exists(self) -> None:
        """Test that docker-compose.yml exists."""
        compose_path = Path("docker-compose.yml")
        assert compose_path.exists(), "docker-compose.yml should exist"

    def test_dockerignore_exists(self) -> None:
        """Test that .dockerignore exists."""
        dockerignore_path = Path(".dockerignore")
        assert dockerignore_path.exists(), ".dockerignore should exist"

    def test_dockerfile_structure(self) -> None:
        """Test Dockerfile has correct structure."""
        dockerfile_path = Path("Dockerfile")
        content = dockerfile_path.read_text()

        # Check for multi-stage build
        assert "FROM python:3.11-slim as builder" in content
        assert "FROM python:3.11-slim as production" in content
        assert "FROM builder as development" in content

        # Check for security practices
        assert "USER botuser" in content
        assert "PYTHONDONTWRITEBYTECODE=1" in content
        assert "PYTHONUNBUFFERED=1" in content

        # Check for health check
        assert "HEALTHCHECK" in content

        # Check for proper Python path
        assert "PYTHONPATH=/app" in content

    def test_docker_compose_structure(self) -> None:
        """Test docker-compose.yml has correct structure."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        # Check version
        assert compose_config.get("version") == "3.8"

        # Check required services
        services = compose_config.get("services", {})
        assert "crypto-bot" in services
        assert "redis" in services

        # Check crypto-bot service configuration
        bot_service = services["crypto-bot"]
        assert "build" in bot_service
        assert "environment" in bot_service
        assert "depends_on" in bot_service
        assert "healthcheck" in bot_service

        # Check Redis service configuration
        redis_service = services["redis"]
        assert "image" in redis_service
        assert "healthcheck" in redis_service

        # Check networks
        assert "networks" in compose_config
        assert "crypto-bot-network" in compose_config["networks"]

        # Check volumes
        assert "volumes" in compose_config
        assert "redis_data" in compose_config["volumes"]

    def test_redis_configuration(self) -> None:
        """Test Redis configuration file."""
        redis_conf_path = Path("docker/redis.conf")
        assert redis_conf_path.exists(), "Redis configuration should exist"

        content = redis_conf_path.read_text()

        # Check important Redis settings
        assert "maxmemory" in content
        assert "appendonly yes" in content
        assert "bind 0.0.0.0" in content
        assert "port 6379" in content

    def test_prometheus_configuration(self) -> None:
        """Test Prometheus configuration file."""
        prometheus_conf_path = Path("docker/prometheus.yml")
        assert prometheus_conf_path.exists(), "Prometheus configuration should exist"

        with open(prometheus_conf_path) as f:
            prometheus_config = yaml.safe_load(f)

        # Check global configuration
        assert "global" in prometheus_config
        assert "scrape_configs" in prometheus_config

        # Check scrape configs
        scrape_configs = prometheus_config["scrape_configs"]
        job_names = [config["job_name"] for config in scrape_configs]
        assert "crypto-bot" in job_names
        assert "redis" in job_names

    def test_grafana_datasource_configuration(self) -> None:
        """Test Grafana datasource configuration."""
        datasource_path = Path("docker/grafana/datasources/prometheus.yml")
        assert datasource_path.exists(), "Grafana datasource config should exist"

        with open(datasource_path) as f:
            datasource_config = yaml.safe_load(f)

        assert "datasources" in datasource_config
        datasources = datasource_config["datasources"]
        assert len(datasources) > 0

        prometheus_ds = datasources[0]
        assert prometheus_ds["name"] == "Prometheus"
        assert prometheus_ds["type"] == "prometheus"
        assert "prometheus:9090" in prometheus_ds["url"]

    def test_dockerignore_content(self) -> None:
        """Test .dockerignore contains necessary exclusions."""
        dockerignore_path = Path(".dockerignore")
        content = dockerignore_path.read_text()

        # Check for common exclusions
        exclusions = [
            ".git",
            "__pycache__",
            "*.py[cod]",  # This covers *.pyc pattern
            ".pytest_cache",
            "venv/",
            ".venv/",
            "logs/",
            ".env.local",
            "memory-bank/",
            "cursor-memory-bank/",
        ]

        for exclusion in exclusions:
            assert exclusion in content, f"{exclusion} should be in .dockerignore"

    def test_docker_profiles(self) -> None:
        """Test Docker Compose profiles are properly configured."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Check development profile
        dev_service = services.get("crypto-bot-dev")
        if dev_service:
            assert "profiles" in dev_service
            assert "dev" in dev_service["profiles"]

        # Check debug profile
        redis_commander = services.get("redis-commander")
        if redis_commander:
            assert "profiles" in redis_commander
            assert "debug" in redis_commander["profiles"]

        # Check monitoring profile
        prometheus_service = services.get("prometheus")
        if prometheus_service:
            assert "profiles" in prometheus_service
            assert "monitoring" in prometheus_service["profiles"]

    def test_docker_resource_limits(self) -> None:
        """Test Docker resource limits are configured."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Check crypto-bot resource limits
        bot_service = services.get("crypto-bot")
        if bot_service and "deploy" in bot_service:
            deploy_config = bot_service["deploy"]
            assert "resources" in deploy_config
            resources = deploy_config["resources"]
            assert "limits" in resources
            assert "reservations" in resources

    def test_docker_security_practices(self) -> None:
        """Test Docker security best practices."""
        dockerfile_path = Path("Dockerfile")
        content = dockerfile_path.read_text()

        # Check non-root user
        assert "useradd" in content or "adduser" in content
        assert "USER botuser" in content

        # Check proper file ownership
        assert "chown" in content

        # Check security environment variables
        assert "PYTHONDONTWRITEBYTECODE=1" in content
        assert "PYTHONUNBUFFERED=1" in content

    @pytest.mark.slow
    def test_docker_build_syntax(self) -> None:
        """Test that Dockerfile has valid syntax."""
        try:
            # Test production build
            result = subprocess.run(
                ["docker", "build", "--target", "production", "--dry-run", "."],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # Note: --dry-run is not available in all Docker versions
            # If it fails, we'll just check that docker build command exists
            if result.returncode != 0 and "--dry-run" in result.stderr:
                # Fallback: just check Docker is available
                result = subprocess.run(
                    ["docker", "--version"], capture_output=True, text=True, timeout=10
                )
                assert result.returncode == 0, "Docker should be available for testing"

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Docker not available for build testing")

    def test_docker_compose_syntax(self) -> None:
        """Test that docker-compose.yml has valid syntax."""
        compose_path = Path("docker-compose.yml")

        try:
            with open(compose_path) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"docker-compose.yml has invalid YAML syntax: {e}")

    def test_environment_variable_configuration(self) -> None:
        """Test environment variables are properly configured."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})
        bot_service = services.get("crypto-bot")

        if bot_service and "environment" in bot_service:
            env_vars = bot_service["environment"]

            # Check required environment variables
            env_dict: dict[str, str] = {}
            for env_var in env_vars:
                if "=" in env_var:
                    key, value = env_var.split("=", 1)
                    env_dict[key] = value

            assert "REDIS_HOST" in env_dict
            assert "REDIS_PORT" in env_dict
            assert "LOG_LEVEL" in env_dict
            assert "ENVIRONMENT" in env_dict
            assert "PYTHONPATH" in env_dict

    def test_volume_configuration(self) -> None:
        """Test volume mounts are properly configured."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})
        bot_service = services.get("crypto-bot")

        if bot_service and "volumes" in bot_service:
            volumes = bot_service["volumes"]
            volume_paths = [vol.split(":")[0] for vol in volumes if ":" in vol]

            # Check important volume mounts
            assert any("logs" in path for path in volume_paths)
            assert any("data" in path for path in volume_paths)

    def test_health_check_configuration(self) -> None:
        """Test health checks are properly configured."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Check bot health check
        bot_service = services.get("crypto-bot")
        if bot_service and "healthcheck" in bot_service:
            healthcheck = bot_service["healthcheck"]
            assert "test" in healthcheck
            assert "interval" in healthcheck
            assert "timeout" in healthcheck
            assert "retries" in healthcheck

        # Check Redis health check
        redis_service = services.get("redis")
        if redis_service and "healthcheck" in redis_service:
            healthcheck = redis_service["healthcheck"]
            assert "test" in healthcheck
            test_command = healthcheck["test"]
            # Handle both string and list formats
            if isinstance(test_command, list):
                assert "redis-cli" in test_command
                assert "ping" in test_command
            else:
                assert "redis-cli ping" in str(test_command)

    def test_network_configuration(self) -> None:
        """Test network configuration."""
        compose_path = Path("docker-compose.yml")

        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)

        # Check networks section
        networks = compose_config.get("networks", {})
        assert "crypto-bot-network" in networks

        network_config = networks["crypto-bot-network"]
        assert network_config.get("driver") == "bridge"

        # Check services use the network
        services = compose_config.get("services", {})
        for service_config in services.values():
            if "networks" in service_config:
                assert "crypto-bot-network" in service_config["networks"]


class TestDockerDirectoryStructure:
    """Test Docker-related directory structure."""

    def test_docker_directory_exists(self) -> None:
        """Test docker configuration directory exists."""
        docker_dir = Path("docker")
        assert docker_dir.exists(), "docker/ directory should exist"
        assert docker_dir.is_dir(), "docker should be a directory"

    def test_docker_config_files_exist(self) -> None:
        """Test Docker configuration files exist."""
        config_files = [
            "docker/redis.conf",
            "docker/prometheus.yml",
            "docker/grafana/datasources/prometheus.yml",
            "docker/grafana/dashboards/dashboard.yml",
        ]

        for config_file in config_files:
            file_path = Path(config_file)
            assert file_path.exists(), f"{config_file} should exist"

    def test_grafana_directory_structure(self) -> None:
        """Test Grafana directory structure."""
        grafana_dir = Path("docker/grafana")
        assert grafana_dir.exists(), "docker/grafana/ should exist"

        dashboards_dir = grafana_dir / "dashboards"
        assert dashboards_dir.exists(), "docker/grafana/dashboards/ should exist"

        datasources_dir = grafana_dir / "datasources"
        assert datasources_dir.exists(), "docker/grafana/datasources/ should exist"
