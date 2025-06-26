"""
Unit tests for development environment configuration.

Tests that all development tools are properly configured and working.
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestDevelopmentEnvironment:
    """Test development environment setup."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent.parent

    def test_pyproject_toml_exists(self) -> None:
        """Test that pyproject.toml exists and is valid."""
        self.setUp()

        pyproject_file = self.project_root / "pyproject.toml"
        assert pyproject_file.exists(), "pyproject.toml does not exist"

        # Test that it's valid TOML
        import tomllib

        with open(pyproject_file, "rb") as f:
            config = tomllib.load(f)

        # Check required sections
        assert "project" in config, "Missing [project] section"
        assert "tool" in config, "Missing [tool] section"
        assert "black" in config["tool"], "Missing [tool.black] section"
        assert "isort" in config["tool"], "Missing [tool.isort] section"
        assert "ruff" in config["tool"], "Missing [tool.ruff] section"
        assert "mypy" in config["tool"], "Missing [tool.mypy] section"
        assert "pytest" in config["tool"], "Missing [tool.pytest] section"

    def test_pre_commit_config_exists(self) -> None:
        """Test that pre-commit configuration exists."""
        self.setUp()

        pre_commit_file = self.project_root / ".pre-commit-config.yaml"
        assert pre_commit_file.exists(), ".pre-commit-config.yaml does not exist"

        # Test that it's valid YAML
        import yaml  # type: ignore[import-untyped]

        with open(pre_commit_file) as f:
            config = yaml.safe_load(f)

        assert "repos" in config, "Missing repos section in pre-commit config"
        assert len(config["repos"]) > 0, "No pre-commit hooks configured"

    def test_makefile_exists(self) -> None:
        """Test that Makefile exists with required targets."""
        self.setUp()

        makefile = self.project_root / "Makefile"
        assert makefile.exists(), "Makefile does not exist"

        content = makefile.read_text()

        # Check for required targets
        required_targets = [
            "help",
            "install",
            "install-dev",
            "test",
            "test-cov",
            "lint",
            "format",
            "type-check",
            "pre-commit",
            "clean",
            "run",
        ]

        for target in required_targets:
            assert f"{target}:" in content, f"Missing Makefile target: {target}"

    def test_development_dependencies_installed(self) -> None:
        """Test that development dependencies are installed."""
        self.setUp()

        # Check that key development tools are available
        dev_tools = ["black", "isort", "ruff", "mypy", "pytest", "pre_commit"]

        for tool in dev_tools:
            result = subprocess.run(
                [sys.executable, "-m", tool, "--version"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            assert (
                result.returncode == 0
            ), f"Development tool {tool} is not installed or not working"

    def test_black_configuration(self) -> None:
        """Test that Black is properly configured."""
        self.setUp()

        # Test that Black can run without errors
        result = subprocess.run(
            [sys.executable, "-m", "black", "--check", "--diff", "src/", "tests/"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        # Should return 0 (no changes needed) since we formatted the code
        assert result.returncode == 0, f"Black formatting issues: {result.stdout}"

    def test_isort_configuration(self) -> None:
        """Test that isort is properly configured."""
        self.setUp()

        # Test that isort can run without errors
        result = subprocess.run(
            [sys.executable, "-m", "isort", "--check-only", "--diff", "src/", "tests/"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        assert result.returncode == 0, f"isort import sorting issues: {result.stdout}"

    def test_ruff_configuration(self) -> None:
        """Test that Ruff is properly configured."""
        self.setUp()

        # Test that Ruff can run without errors
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "src/", "tests/"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        assert result.returncode == 0, f"Ruff linting issues: {result.stdout}"

    def test_mypy_configuration(self) -> None:
        """Test that MyPy is properly configured."""
        self.setUp()

        # Test that MyPy can run without errors
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        assert result.returncode == 0, f"MyPy type checking issues: {result.stdout}"

    def test_pytest_configuration(self) -> None:
        """Test that pytest is properly configured."""
        self.setUp()

        # Test that pytest can discover and run tests
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        assert result.returncode == 0, f"Pytest configuration issues: {result.stdout}"
        assert "test" in result.stdout.lower(), "No tests discovered by pytest"

    def test_pre_commit_hooks_installed(self) -> None:
        """Test that pre-commit hooks are installed."""
        self.setUp()

        # Check if pre-commit is installed in git hooks
        git_hooks_dir = self.project_root / ".git" / "hooks"
        pre_commit_hook = git_hooks_dir / "pre-commit"

        assert pre_commit_hook.exists(), "Pre-commit hook is not installed"

        # Test that pre-commit can run
        result = subprocess.run(
            [sys.executable, "-m", "pre_commit", "--version"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        assert result.returncode == 0, f"Pre-commit is not working: {result.stderr}"

    def test_development_workflow_integration(self) -> None:
        """Test that all development tools work together."""
        self.setUp()

        # Test the complete development workflow
        tools_and_commands = [
            (["python", "-m", "black", "--check", "src/"], "Black formatting"),
            (["python", "-m", "isort", "--check-only", "src/"], "isort import sorting"),
            (["python", "-m", "ruff", "check", "src/"], "Ruff linting"),
            (
                ["python", "-m", "mypy", "src/", "--ignore-missing-imports"],
                "MyPy type checking",
            ),
        ]

        for command, description in tools_and_commands:
            result = subprocess.run(
                command, capture_output=True, text=True, cwd=self.project_root
            )

            assert (
                result.returncode == 0
            ), f"{description} failed: {result.stdout}\n{result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__])
