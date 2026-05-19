"""Tests for vault management."""

import subprocess
from pathlib import Path

import pytest

from envseal.config import Config
from envseal.vault import VaultManager


def test_get_vault_path_for_env(temp_dir):
    """Test getting vault path for a specific env file."""
    vault_path = temp_dir / "vault"
    config = Config(vault_path=vault_path)

    vault = VaultManager(config)
    path = vault.get_vault_path("my-repo", "prod")

    assert path == vault_path / "secrets" / "my-repo" / "prod.env"


def test_get_vault_path_with_subdir(temp_dir):
    """A nested env file maps to a vault path mirroring its location in the repo."""
    vault_path = temp_dir / "vault"
    vault = VaultManager(Config(vault_path=vault_path))
    secrets = vault_path / "secrets" / "my-repo"

    assert vault.get_vault_path("my-repo", "local") == secrets / "local.env"
    assert vault.get_vault_path("my-repo", "local", ".") == secrets / "local.env"
    assert (
        vault.get_vault_path("my-repo", "local", "frontend") == secrets / "frontend" / "local.env"
    )


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
        },
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


def test_is_git_repo_true(mock_vault):
    """is_git_repo returns True for an initialized vault repository."""
    vault = VaultManager(Config(vault_path=mock_vault))
    assert vault.is_git_repo() is True


def test_is_git_repo_false(temp_dir):
    """is_git_repo returns False for a plain (non-Git) directory."""
    plain = temp_dir / "plain"
    plain.mkdir()
    vault = VaultManager(Config(vault_path=plain))
    assert vault.is_git_repo() is False


def test_git_commit_creates_commit(mock_vault):
    """git_commit stages and commits changes, returning True."""
    vault = VaultManager(Config(vault_path=mock_vault))
    (mock_vault / "secrets" / "demo.env").write_text("ENC=1\n")

    assert vault.git_commit("envseal test commit") is True

    log = subprocess.run(
        ["git", "-C", str(mock_vault), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "envseal test commit" in log.stdout


def test_git_commit_nothing_to_commit(mock_vault):
    """git_commit returns False when the working tree is clean."""
    vault = VaultManager(Config(vault_path=mock_vault))
    (mock_vault / "secrets" / "demo.env").write_text("ENC=1\n")
    vault.git_commit("first")

    assert vault.git_commit("second") is False


def test_git_push_without_remote_raises(mock_vault):
    """git_push raises RuntimeError when no remote is configured."""
    vault = VaultManager(Config(vault_path=mock_vault))
    (mock_vault / "secrets" / "demo.env").write_text("ENC=1\n")
    vault.git_commit("commit before push")

    with pytest.raises(RuntimeError, match="git push failed"):
        vault.git_push()


def test_git_push_to_remote(mock_vault, temp_dir):
    """git_push succeeds and delivers commits when an upstream remote is set."""
    remote = temp_dir / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    vault = VaultManager(Config(vault_path=mock_vault))
    (mock_vault / "secrets" / "demo.env").write_text("ENC=1\n")
    vault.git_commit("first commit")

    # wire up the remote and an upstream tracking branch
    subprocess.run(
        ["git", "-C", str(mock_vault), "remote", "add", "origin", str(remote)],
        check=True,
        capture_output=True,
    )
    branch = subprocess.run(
        ["git", "-C", str(mock_vault), "branch", "--show-current"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(mock_vault), "push", "-u", "origin", branch],
        check=True,
        capture_output=True,
    )

    # a new commit pushed via the helper reaches the remote
    (mock_vault / "secrets" / "demo2.env").write_text("ENC=2\n")
    vault.git_commit("second commit")
    vault.git_push()

    log = subprocess.run(
        ["git", "-C", str(remote), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "second commit" in log.stdout
