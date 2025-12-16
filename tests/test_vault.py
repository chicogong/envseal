"""Tests for vault management."""

from pathlib import Path

from envseal.config import Config
from envseal.vault import VaultManager


def test_get_vault_path_for_env(temp_dir):
    """Test getting vault path for a specific env file."""
    vault_path = temp_dir / "vault"
    config = Config(vault_path=vault_path)

    vault = VaultManager(config)
    path = vault.get_vault_path("my-repo", "prod")

    assert path == vault_path / "secrets" / "my-repo" / "prod.env"


def test_ensure_vault_structure(temp_dir):
    """Test creating vault directory structure."""
    vault_path = temp_dir / "vault"
    config = Config(vault_path=vault_path)

    vault = VaultManager(config)
    vault.ensure_vault_structure()

    assert (vault_path / "secrets").exists()
    assert (vault_path / "secrets").is_dir()


def test_map_env_filename():
    """Test mapping .env filename to environment name."""
    vault = VaultManager(Config(vault_path=Path("/tmp")))

    assert vault.map_env_filename(".env") == "local"
    assert vault.map_env_filename(".env.prod") == "prod"
    assert vault.map_env_filename(".env.production") == "prod"
    assert vault.map_env_filename(".env.custom") == "custom"


def test_map_env_filename_with_custom_mapping(temp_dir):
    """Test mapping with custom env_mapping in config."""
    vault_path = temp_dir / "vault"
    config = Config(
        vault_path=vault_path,
        env_mapping={
            ".env": "local",
            ".env.dev": "development",
            ".env.prod": "production",
        }
    )

    vault = VaultManager(config)

    assert vault.map_env_filename(".env") == "local"
    assert vault.map_env_filename(".env.dev") == "development"
    assert vault.map_env_filename(".env.prod") == "production"


def test_get_repo_vault_dir(temp_dir):
    """Test getting vault directory for a specific repo."""
    vault_path = temp_dir / "vault"
    config = Config(vault_path=vault_path)

    vault = VaultManager(config)
    repo_dir = vault.get_repo_vault_dir("my-repo")

    assert repo_dir == vault_path / "secrets" / "my-repo"


def test_vault_path_with_nested_repo_name(temp_dir):
    """Test vault path handling with repo names containing special chars."""
    vault_path = temp_dir / "vault"
    config = Config(vault_path=vault_path)

    vault = VaultManager(config)
    path = vault.get_vault_path("my-org/my-repo", "prod")

    # Path should handle the slash in repo name
    assert "my-org/my-repo" in str(path)
    assert path.name == "prod.env"


def test_ensure_vault_structure_creates_parent_dirs(temp_dir):
    """Test that ensure_vault_structure creates all parent directories."""
    vault_path = temp_dir / "deeply" / "nested" / "vault"
    config = Config(vault_path=vault_path)

    vault = VaultManager(config)
    vault.ensure_vault_structure()

    assert vault_path.exists()
    assert (vault_path / "secrets").exists()
