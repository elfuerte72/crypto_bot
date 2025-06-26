"""
Unit tests for project structure setup.

Tests that all required directories and files are created properly.
"""

import pytest
from pathlib import Path


class TestProjectStructure:
    """Test project structure setup."""
    
    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent.parent
        
    def test_main_directories_exist(self):
        """Test that main project directories exist."""
        self.setUp()
        
        required_dirs = [
            "src",
            "src/bot", 
            "src/bot/handlers",
            "src/bot/keyboards",
            "src/bot/states",
            "src/services",
            "src/config",
            "src/models",
            "tests",
            "tests/unit",
            "tests/unit/bot",
            "tests/unit/services", 
            "tests/integration",
            "docker",
            "docs"
        ]
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            assert full_path.exists(), f"Directory {dir_path} does not exist"
            assert full_path.is_dir(), f"{dir_path} is not a directory"
    
    def test_init_files_exist(self):
        """Test that __init__.py files exist in Python packages."""
        self.setUp()
        
        init_files = [
            "src/__init__.py",
            "src/bot/__init__.py",
            "src/bot/handlers/__init__.py",
            "src/bot/keyboards/__init__.py", 
            "src/bot/states/__init__.py",
            "src/services/__init__.py",
            "src/config/__init__.py",
            "src/models/__init__.py",
            "tests/__init__.py",
            "tests/unit/__init__.py",
            "tests/unit/bot/__init__.py",
            "tests/unit/services/__init__.py",
            "tests/integration/__init__.py"
        ]
        
        for init_file in init_files:
            full_path = self.project_root / init_file
            assert full_path.exists(), f"Init file {init_file} does not exist"
            assert full_path.is_file(), f"{init_file} is not a file"
    
    def test_main_entry_point_exists(self):
        """Test that main.py entry point exists."""
        self.setUp()
        
        main_file = self.project_root / "main.py"
        assert main_file.exists(), "main.py does not exist"
        assert main_file.is_file(), "main.py is not a file"
        
        # Check that main.py has required content
        content = main_file.read_text()
        assert "async def main()" in content, "main.py missing main() function"
        assert "if __name__ == \"__main__\":" in content, "main.py missing entry point"
    
    def test_project_structure_completeness(self):
        """Test that project structure is complete for crypto bot requirements."""
        self.setUp()
        
        # Test that we have all required components for the crypto bot
        required_structure = {
            "src/bot": "Bot layer components",
            "src/services": "Business logic services", 
            "src/config": "Configuration management",
            "src/models": "Data models and schemas",
            "tests/unit/bot": "Bot unit tests",
            "tests/unit/services": "Service unit tests",
            "tests/integration": "Integration tests",
            "docker": "Container configuration",
            "docs": "Documentation"
        }
        
        for path, description in required_structure.items():
            full_path = self.project_root / path
            assert full_path.exists(), f"Missing {description} directory: {path}"
    
    def test_directory_permissions(self):
        """Test that directories have proper permissions."""
        self.setUp()
        
        # Test that directories are readable and writable
        test_dirs = ["src", "tests", "docker", "docs"]
        
        for dir_name in test_dirs:
            dir_path = self.project_root / dir_name
            assert dir_path.exists(), f"Directory {dir_name} does not exist"
            
            # Test we can read the directory
            try:
                list(dir_path.iterdir())
            except PermissionError:
                pytest.fail(f"Cannot read directory {dir_name}")
            
            # Test we can write to the directory (create temp file)
            try:
                temp_file = dir_path / ".test_write_permission"
                temp_file.touch()
                temp_file.unlink()  # Clean up
            except PermissionError:
                pytest.fail(f"Cannot write to directory {dir_name}")


if __name__ == "__main__":
    pytest.main([__file__])