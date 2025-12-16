"""Tests for configuration management."""

from pathlib import Path

import pytest

from envseal.config import Config, Repo


def test_config_load_from_dict(temp_dir):
    """Test loading config from dictionary."""
    config_dict = {
        "vault_path": str(temp_dir / "vault"),
        "repos": [
            {"name": "project1", "path": str(temp_dir / "project1")},
        ],
        "env_mapping": {
            ".env": "local",
            ".env.prod": "prod",
        },
        "scan": {
            "include_patterns": [".env", ".env.*"],
            "exclude_patterns": [".env.example"],
            "ignore_dirs": [".git", "node_modules"],
        },
    }

    config = Config.from_dict(config_dict)

    assert config.vault_path == Path(temp_dir / "vault")
    assert len(config.repos) == 1
    assert config.repos[0].name == "project1"
    assert config.env_mapping[".env"] == "local"


def test_config_save_and_load(temp_dir):
    """Test saving and loading config to/from file."""
    config_path = temp_dir / "config.yaml"

    config = Config(
        vault_path=temp_dir / "vault",
        repos=[Repo(name="test", path=temp_dir / "test")],
    )

    config.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.vault_path == config.vault_path
    assert len(loaded.repos) == 1


def test_config_load_file_not_found(temp_dir):
    """Test loading config from non-existent file."""
    config_path = temp_dir / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError) as exc_info:
        Config.load(config_path)

    assert "Config file not found" in str(exc_info.value)
    assert str(config_path) in str(exc_info.value)


def test_config_load_empty_file(temp_dir):
    """Test loading config from empty file."""
    config_path = temp_dir / "empty.yaml"
    config_path.write_text("")

    with pytest.raises(ValueError) as exc_info:
        Config.load(config_path)

    assert "Config file is empty or invalid" in str(exc_info.value)


def test_config_load_invalid_yaml(temp_dir):
    """Test loading config from file with invalid YAML."""
    config_path = temp_dir / "invalid.yaml"
    # Use unclosed brackets to create invalid YAML
    config_path.write_text("vault_path: /tmp/vault\nrepos: [unclosed")

    with pytest.raises(ValueError) as exc_info:
        Config.load(config_path)

    assert "Invalid YAML in config file" in str(exc_info.value)


def test_config_load_missing_vault_path(temp_dir):
    """Test loading config without required vault_path field."""
    config_path = temp_dir / "no_vault.yaml"
    config_path.write_text("repos: []\n")

    with pytest.raises(ValueError) as exc_info:
        Config.load(config_path)

    assert "Config file missing required field: vault_path" in str(exc_info.value)


def test_config_save_to_readonly_location(temp_dir):
    """Test saving config to read-only location."""
    config = Config(vault_path=temp_dir / "vault")

    # Create a directory and make it read-only
    readonly_dir = temp_dir / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)

    config_path = readonly_dir / "config.yaml"

    try:
        with pytest.raises(OSError) as exc_info:
            config.save(config_path)

        assert "Failed to save config" in str(exc_info.value)
    finally:
        # Cleanup: restore permissions
        readonly_dir.chmod(0o755)
