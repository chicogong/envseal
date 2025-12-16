"""Pytest configuration and shared fixtures."""

import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_repo(temp_dir: Path) -> Path:
    """Create a mock Git repository with .env files."""
    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)

    # Create .env files
    (repo_path / ".env").write_text("DATABASE_URL=postgres://localhost/db\nAPI_KEY=test123\n")
    (repo_path / ".env.prod").write_text("DATABASE_URL=postgres://prod/db\nAPI_KEY=prod456\n")

    return repo_path


@pytest.fixture
def mock_vault(temp_dir: Path) -> Path:
    """Create a mock vault repository."""
    vault_path = temp_dir / "secrets-vault"
    vault_path.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=vault_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=vault_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=vault_path, check=True)

    # Create directories
    (vault_path / "secrets").mkdir()

    return vault_path
