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
