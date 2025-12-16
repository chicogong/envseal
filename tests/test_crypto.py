"""Tests for cryptographic key management."""

import subprocess

import pytest

from envseal.crypto import AgeKeyManager


# Check if age-keygen is installed
def has_age_keygen():
    """Check if age-keygen is available."""
    try:
        subprocess.run(["age-keygen", "-h"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


requires_age = pytest.mark.skipif(
    not has_age_keygen(),
    reason="age-keygen CLI not installed"
)


@requires_age
def test_generate_age_key(temp_dir):
    """Test generating age key pair."""
    key_file = temp_dir / "keys.txt"

    manager = AgeKeyManager()
    public_key = manager.generate_key(key_file)

    assert key_file.exists()
    assert public_key.startswith("age1")

    # Check file permissions (should be 600)
    assert oct(key_file.stat().st_mode)[-3:] == "600"


@requires_age
def test_get_public_key_from_file(temp_dir):
    """Test extracting public key from existing key file."""
    key_file = temp_dir / "keys.txt"

    # Generate key first
    manager = AgeKeyManager()
    expected_public = manager.generate_key(key_file)

    # Extract public key
    actual_public = manager.get_public_key(key_file)

    assert actual_public == expected_public


def test_get_default_key_path():
    """Test getting default age key path."""
    manager = AgeKeyManager()
    path = manager.get_default_key_path()

    assert "sops/age/keys.txt" in str(path)
    assert path.parent.parent.name == "sops"


@requires_age
def test_key_exists(temp_dir):
    """Test checking if key exists."""
    key_file = temp_dir / "keys.txt"
    manager = AgeKeyManager()

    # Key doesn't exist yet
    assert not manager.key_exists(key_file)

    # Generate key
    manager.generate_key(key_file)

    # Key exists now
    assert manager.key_exists(key_file)


def test_get_public_key_missing_file(temp_dir):
    """Test getting public key from non-existent file raises error."""
    key_file = temp_dir / "nonexistent.txt"
    manager = AgeKeyManager()

    with pytest.raises(FileNotFoundError):
        manager.get_public_key(key_file)
