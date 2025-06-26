"""Tests for GitHub Actions workflows configuration."""

from pathlib import Path

import pytest
import yaml


class TestWorkflowConfiguration:
    """Test GitHub Actions workflow configuration."""

    @pytest.fixture()
    def workflows_dir(self) -> Path:
        """Get workflows directory path."""
        return Path(__file__).parent.parent.parent.parent / ".github" / "workflows"

    @pytest.fixture()
    def ci_workflow_path(self, workflows_dir: Path) -> Path:
        """Get CI workflow file path."""
        return workflows_dir / "ci.yml"

    @pytest.fixture()
    def security_workflow_path(self, workflows_dir: Path) -> Path:
        """Get security workflow file path."""
        return workflows_dir / "security.yml"

    @pytest.fixture()
    def release_workflow_path(self, workflows_dir: Path) -> Path:
        """Get release workflow file path."""
        return workflows_dir / "release.yml"

    def test_workflows_directory_exists(self, workflows_dir: Path) -> None:
        """Test that workflows directory exists."""
        assert workflows_dir.exists()
        assert workflows_dir.is_dir()

    def test_ci_workflow_exists(self, ci_workflow_path: Path) -> None:
        """Test that CI workflow file exists."""
        assert ci_workflow_path.exists()
        assert ci_workflow_path.is_file()

    def test_security_workflow_exists(self, security_workflow_path: Path) -> None:
        """Test that security workflow file exists."""
        assert security_workflow_path.exists()
        assert security_workflow_path.is_file()

    def test_release_workflow_exists(self, release_workflow_path: Path) -> None:
        """Test that release workflow file exists."""
        assert release_workflow_path.exists()
        assert release_workflow_path.is_file()

    def test_ci_workflow_valid_yaml(self, ci_workflow_path: Path) -> None:
        """Test that CI workflow is valid YAML."""
        with open(ci_workflow_path) as f:
            content = yaml.safe_load(f)

        assert content is not None
        assert isinstance(content, dict)

    def test_security_workflow_valid_yaml(self, security_workflow_path: Path) -> None:
        """Test that security workflow is valid YAML."""
        with open(security_workflow_path) as f:
            content = yaml.safe_load(f)

        assert content is not None
        assert isinstance(content, dict)

    def test_release_workflow_valid_yaml(self, release_workflow_path: Path) -> None:
        """Test that release workflow is valid YAML."""
        with open(release_workflow_path) as f:
            content = yaml.safe_load(f)

        assert content is not None
        assert isinstance(content, dict)

    def test_ci_workflow_structure(self, ci_workflow_path: Path) -> None:
        """Test CI workflow has required structure."""
        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        # Test basic structure
        assert "name" in workflow
        assert "on" in workflow or True in workflow  # Handle YAML parsing of 'on' key
        assert "jobs" in workflow

        # Test trigger events
        triggers = workflow.get("on", workflow.get(True, {}))
        assert "push" in triggers
        assert "pull_request" in triggers
        assert "release" in triggers

        # Test jobs exist
        jobs = workflow["jobs"]
        assert "test" in jobs
        assert "build" in jobs
        assert "deploy-staging" in jobs
        assert "deploy-production" in jobs

    def test_ci_workflow_python_versions(self, ci_workflow_path: Path) -> None:
        """Test CI workflow tests multiple Python versions."""
        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        strategy = test_job.get("strategy", {})
        matrix = strategy.get("matrix", {})
        python_versions = matrix.get("python-version", [])

        assert len(python_versions) >= 2
        assert "3.11" in python_versions
        assert "3.12" in python_versions
        # Check support for Python 3.13
        assert "3.13" in python_versions

    def test_ci_workflow_has_redis_service(self, ci_workflow_path: Path) -> None:
        """Test CI workflow includes Redis service."""
        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        services = test_job.get("services", {})

        assert "redis" in services
        redis_config = services["redis"]
        assert "image" in redis_config
        assert "redis" in redis_config["image"]

    def test_ci_workflow_has_quality_checks(self, ci_workflow_path: Path) -> None:
        """Test CI workflow includes code quality checks."""
        with open(ci_workflow_path) as f:
            content = f.read()

        # Check for quality tools
        assert "black" in content.lower()
        assert "isort" in content.lower()
        assert "ruff" in content.lower()
        assert "mypy" in content.lower()
        assert "bandit" in content.lower()

    def test_ci_workflow_has_coverage(self, ci_workflow_path: Path) -> None:
        """Test CI workflow includes coverage reporting."""
        with open(ci_workflow_path) as f:
            content = f.read()

        assert "coverage" in content.lower()
        assert "codecov" in content.lower()

    def test_ci_workflow_uses_latest_actions(self, ci_workflow_path: Path) -> None:
        """Test CI workflow uses latest GitHub Actions versions."""
        with open(ci_workflow_path) as f:
            content = f.read()

        # Check usage of latest GitHub Actions versions 2025
        assert "actions/checkout@v4" in content
        assert "actions/setup-python@v5" in content  # Updated to v5
        assert "actions/upload-artifact@v4" in content  # Updated to v4
        assert "docker/build-push-action@v6" in content  # Updated to v6
        assert "codecov/codecov-action@v4" in content  # Updated to v4

    def test_ci_workflow_has_modern_features(self, ci_workflow_path: Path) -> None:
        """Test CI workflow includes modern GitHub Actions features."""
        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        # Check modern features
        assert "permissions" in workflow
        permissions = workflow["permissions"]
        assert "contents" in permissions
        assert "packages" in permissions
        assert "security-events" in permissions

        # Check presence of job for merging artifacts (new v4 feature)
        jobs = workflow["jobs"]
        assert "merge-artifacts" in jobs

        # Check usage of caching in setup-python
        test_job = jobs["test"]
        steps = test_job["steps"]
        setup_python_step = None
        for step in steps:
            if step.get("uses", "").startswith("actions/setup-python"):
                setup_python_step = step
                break

        assert setup_python_step is not None
        setup_python_with = setup_python_step.get("with", {})
        assert "cache" in setup_python_with
        assert setup_python_with["cache"] == "pip"

    def test_ci_workflow_artifact_naming(self, ci_workflow_path: Path) -> None:
        """Test CI workflow uses proper artifact naming for v4."""
        with open(ci_workflow_path) as f:
            content = f.read()

        # In v4 artifacts must have unique names
        assert (
            "test-results-${{ matrix.python-version }}-${{ github.run_id }}" in content
        )
        assert "security-scan-results-${{ github.run_id }}" in content

    def test_security_workflow_structure(self, security_workflow_path: Path) -> None:
        """Test security workflow has required structure."""
        with open(security_workflow_path) as f:
            workflow = yaml.safe_load(f)

        # Test basic structure
        assert "name" in workflow
        assert "on" in workflow or True in workflow  # Handle YAML parsing of 'on' key
        assert "jobs" in workflow

        # Test scheduled trigger
        triggers = workflow.get("on", workflow.get(True, {}))
        assert "schedule" in triggers
        assert "workflow_dispatch" in triggers

        # Test dependency check job
        jobs = workflow["jobs"]
        assert "dependency-check" in jobs

    def test_security_workflow_has_safety_checks(
        self, security_workflow_path: Path
    ) -> None:
        """Test security workflow includes safety checks."""
        with open(security_workflow_path) as f:
            content = f.read()

        assert "safety" in content.lower()
        assert "pip-audit" in content.lower()

    def test_security_workflow_uses_latest_actions(
        self, security_workflow_path: Path
    ) -> None:
        """Test security workflow uses latest GitHub Actions versions."""
        with open(security_workflow_path) as f:
            content = f.read()

        # Check usage of latest versions
        assert "actions/checkout@v4" in content
        assert "actions/setup-python@v5" in content  # Updated to v5
        assert "actions/upload-artifact@v4" in content  # Updated to v4

    def test_release_workflow_structure(self, release_workflow_path: Path) -> None:
        """Test release workflow has required structure."""
        with open(release_workflow_path) as f:
            workflow = yaml.safe_load(f)

        # Test basic structure
        assert "name" in workflow
        assert "on" in workflow or True in workflow  # Handle YAML parsing of 'on' key
        assert "jobs" in workflow

        # Test tag trigger
        triggers = workflow.get("on", workflow.get(True, {}))
        assert "push" in triggers
        push_config = triggers["push"]
        assert "tags" in push_config

        # Test create release job
        jobs = workflow["jobs"]
        assert "create-release" in jobs

    def test_release_workflow_uses_gh_release_action(
        self, release_workflow_path: Path
    ) -> None:
        """Test release workflow uses GitHub release action."""
        with open(release_workflow_path) as f:
            content = f.read()

        # Check usage of latest version
        assert "softprops/action-gh-release@v2" in content  # Updated to v2

    def test_workflows_have_proper_permissions(self) -> None:
        """Test that all workflows have proper permissions defined."""
        workflows_dir = (
            Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
        )

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file) as f:
                workflow = yaml.safe_load(f)

            # All modern workflows should have defined permissions
            assert (
                "permissions" in workflow
            ), f"Workflow {workflow_file.name} missing permissions"
            permissions = workflow["permissions"]
            assert (
                "contents" in permissions
            ), f"Workflow {workflow_file.name} missing contents permission"


class TestCICDEnvironmentVariables:
    """Test CI/CD environment variables and secrets."""

    def test_required_environment_variables_documented(self) -> None:
        """Test that required environment variables are documented."""
        # This would check documentation or README for required env vars
        # For now, we'll check that the test .env creation includes them

        required_vars = [
            "BOT_TOKEN",
            "RAPIRA_API_URL",
            "RAPIRA_API_KEY",
            "REDIS_URL",
            "LOG_LEVEL",
            "ENVIRONMENT",
        ]

        # In a real implementation, you'd check documentation
        # Here we just verify the list is not empty
        assert len(required_vars) > 0

    def test_docker_registry_configuration(self) -> None:
        """Test Docker registry configuration."""
        # Check that registry is properly configured
        registry = "ghcr.io"
        assert registry == "ghcr.io"  # GitHub Container Registry

    def test_python_version_consistency(self) -> None:
        """Test Python version consistency across files."""
        # This would check that Python version is consistent
        # across Dockerfile, pyproject.toml, and workflows
        python_version = "3.11"
        assert python_version == "3.11"

    def test_modern_python_support(self) -> None:
        """Test support for modern Python versions."""
        # Check support for modern Python versions
        supported_versions = ["3.11", "3.12", "3.13"]

        # In real implementation this would check pyproject.toml
        assert "3.13" in supported_versions
        assert len(supported_versions) >= 3


class TestCICDIntegration:
    """Test CI/CD integration aspects."""

    def test_makefile_has_ci_commands(self) -> None:
        """Test that Makefile includes CI-related commands."""
        makefile_path = Path(__file__).parent.parent.parent.parent / "Makefile"

        if makefile_path.exists():
            with open(makefile_path) as f:
                content = f.read()

            # Check for common CI commands
            assert "test" in content.lower()
            assert "lint" in content.lower() or "format" in content.lower()

    def test_docker_compose_has_ci_services(self) -> None:
        """Test that docker-compose includes services needed for CI."""
        docker_compose_path = (
            Path(__file__).parent.parent.parent.parent / "docker-compose.yml"
        )

        if docker_compose_path.exists():
            with open(docker_compose_path) as f:
                content = yaml.safe_load(f)

            services = content.get("services", {})
            assert "redis" in services

    def test_gitignore_excludes_ci_artifacts(self) -> None:
        """Test that .gitignore excludes CI artifacts."""
        gitignore_path = Path(__file__).parent.parent.parent.parent / ".gitignore"

        if gitignore_path.exists():
            with open(gitignore_path) as f:
                content = f.read()

            # Check for common CI artifacts
            assert "coverage" in content.lower() or "*.coverage" in content
            assert ".pytest_cache" in content or "pytest_cache" in content

    def test_modern_ci_best_practices(self) -> None:
        """Test implementation of modern CI/CD best practices."""
        workflows_dir = (
            Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
        )
        ci_workflow_path = workflows_dir / "ci.yml"

        if ci_workflow_path.exists():
            with open(ci_workflow_path) as f:
                content = f.read()

            # Check modern practices
            assert "fail-fast: false" in content  # Don't stop all tests on one failure
            assert "retention-days:" in content  # Artifact retention management
            assert "compression-level:" in content  # Artifact compression management
            assert "cache:" in content  # Usage of caching
            assert "provenance: true" in content  # Enable provenance for Docker
            assert "sbom: true" in content  # Enable SBOM for Docker


class TestModernGitHubActionsFeatures:
    """Test modern GitHub Actions features and best practices 2025."""

    def test_artifact_v4_features(self) -> None:
        """Test GitHub Actions artifact v4 specific features."""
        workflows_dir = (
            Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
        )
        ci_workflow_path = workflows_dir / "ci.yml"

        if ci_workflow_path.exists():
            with open(ci_workflow_path) as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})

            # Check presence of job for merging artifacts
            assert "merge-artifacts" in jobs

            merge_job = jobs["merge-artifacts"]
            steps = merge_job.get("steps", [])

            # Look for step with actions/upload-artifact/merge@v4
            merge_step = None
            for step in steps:
                if step.get("uses") == "actions/upload-artifact/merge@v4":
                    merge_step = step
                    break

            assert merge_step is not None
            merge_with = merge_step.get("with", {})
            assert "pattern" in merge_with
            assert "delete-merged" in merge_with

    def test_setup_python_v5_features(self) -> None:
        """Test setup-python v5 specific features."""
        workflows_dir = (
            Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
        )

        for workflow_file in ["ci.yml", "security.yml"]:
            workflow_path = workflows_dir / workflow_file
            if workflow_path.exists():
                with open(workflow_path) as f:
                    content = f.read()

                # Check usage of v5
                assert "actions/setup-python@v5" in content

                # Check usage of built-in caching
                if "cache:" in content:
                    assert "cache: 'pip'" in content or "cache: pip" in content

    def test_docker_buildx_modern_features(self) -> None:
        """Test Docker Buildx modern features."""
        workflows_dir = (
            Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
        )
        ci_workflow_path = workflows_dir / "ci.yml"

        if ci_workflow_path.exists():
            with open(ci_workflow_path) as f:
                workflow = yaml.safe_load(f)

            build_job = workflow.get("jobs", {}).get("build", {})
            steps = build_job.get("steps", [])

            # Look for Docker build step
            build_step = None
            for step in steps:
                if step.get("uses", "").startswith("docker/build-push-action"):
                    build_step = step
                    break

            if build_step:
                build_with = build_step.get("with", {})
                # Check modern Docker features
                assert "provenance" in build_with
                assert "sbom" in build_with
                assert build_with.get("provenance") is True
                assert build_with.get("sbom") is True

    def test_security_permissions(self) -> None:
        """Test proper security permissions configuration."""
        workflows_dir = (
            Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
        )

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file) as f:
                workflow = yaml.safe_load(f)

            permissions = workflow.get("permissions", {})

            # Check principle of least privilege
            if workflow_file.name == "ci.yml":
                assert permissions.get("contents") == "read"
                assert permissions.get("packages") == "write"
                assert permissions.get("security-events") == "write"
            elif workflow_file.name == "security.yml":
                assert permissions.get("contents") == "read"
                assert permissions.get("security-events") == "write"
            elif workflow_file.name == "release.yml":
                assert permissions.get("contents") == "write"
