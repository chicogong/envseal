"""Tests for repository and .env file scanning."""

from pathlib import Path
import pytest
from envseal.scanner import Scanner, EnvFile
from envseal.config import Config, ScanConfig


def test_scanner_finds_env_files(mock_repo):
    """Test scanner finds .env files in a repository."""
    scan_config = ScanConfig()
    scanner = Scanner(scan_config)

    env_files = scanner.scan_repo(mock_repo)

    assert len(env_files) == 2
    filenames = {ef.filepath.name for ef in env_files}
    assert ".env" in filenames
    assert ".env.prod" in filenames


def test_scanner_excludes_patterns(temp_dir):
    """Test scanner excludes files matching patterns."""
    repo = temp_dir / "repo"
    repo.mkdir()

    # Create files
    (repo / ".env").write_text("KEY=value")
    (repo / ".env.example").write_text("KEY=example")

    scan_config = ScanConfig(exclude_patterns=[".env.example"])
    scanner = Scanner(scan_config)

    env_files = scanner.scan_repo(repo)

    assert len(env_files) == 1
    assert env_files[0].filepath.name == ".env"


def test_scanner_ignores_directories(temp_dir):
    """Test scanner ignores specified directories."""
    repo = temp_dir / "repo"
    repo.mkdir()
    (repo / "node_modules").mkdir()

    (repo / ".env").write_text("KEY=value")
    (repo / "node_modules" / ".env").write_text("KEY=bad")

    scan_config = ScanConfig(ignore_dirs=["node_modules"])
    scanner = Scanner(scan_config)

    env_files = scanner.scan_repo(repo)

    assert len(env_files) == 1
    assert "node_modules" not in str(env_files[0].filepath)
