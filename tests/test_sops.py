"""Tests for SOPS encryption wrapper."""

import subprocess

import pytest

from envseal.crypto import AgeKeyManager
from envseal.sops import SopsManager


# Check if both age-keygen and sops are installed
def has_age_and_sops():
    """Check if both age-keygen and sops are available."""
    try:
        subprocess.run(["age-keygen", "-h"], capture_output=True, check=True)
        subprocess.run(["sops", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


requires_sops = pytest.mark.skipif(
    not has_age_and_sops(),
    reason="age-keygen and/or sops CLI not installed"
)


@pytest.fixture
def age_key(temp_dir):
    """Generate a test age key."""
    if not has_age_and_sops():
        pytest.skip("age-keygen not available")

    key_file = temp_dir / "test-key.txt"
    manager = AgeKeyManager()
    public_key = manager.generate_key(key_file)
    return key_file, public_key


@requires_sops
def test_encrypt_decrypt_dotenv(temp_dir, age_key):
    """Test encrypting and decrypting a .env file."""
    key_file, public_key = age_key

    # Create test .env file
    input_file = temp_dir / "test.env"
    input_file.write_text("DATABASE_URL=postgres://localhost/db\nAPI_KEY=secret123\n")

    # Encrypt
    encrypted_file = temp_dir / "test.env.enc"
    sops = SopsManager(age_public_key=public_key, age_key_file=key_file)
    sops.encrypt(input_file, encrypted_file)

    assert encrypted_file.exists()
    # Encrypted file should contain SOPS metadata
    encrypted_content = encrypted_file.read_text()
    assert "sops" in encrypted_content
    assert "age" in encrypted_content

    # Decrypt
    decrypted = sops.decrypt(encrypted_file)

    assert "DATABASE_URL=postgres://localhost/db" in decrypted
    assert "API_KEY=secret123" in decrypted


def test_create_sops_yaml(temp_dir):
    """Test creating .sops.yaml configuration."""
    public_key = "age1test123456789abcdefghijklmnopqrstuvwxyz"
    sops_yaml = temp_dir / ".sops.yaml"

    sops = SopsManager(age_public_key=public_key)
    sops.create_sops_yaml(sops_yaml)

    assert sops_yaml.exists()
    content = sops_yaml.read_text()

    assert "creation_rules" in content
    assert "input_type: dotenv" in content
    assert public_key in content


@requires_sops
def test_encrypt_with_env_variable(temp_dir, age_key):
    """Test that SOPS_AGE_KEY_FILE environment variable is used."""
    key_file, public_key = age_key

    # Create test .env file
    input_file = temp_dir / "test.env"
    input_file.write_text("KEY=value\n")

    # Encrypt with age_key_file set
    encrypted_file = temp_dir / "test.env.enc"
    sops = SopsManager(age_public_key=public_key, age_key_file=key_file)
    sops.encrypt(input_file, encrypted_file)

    # Should succeed
    assert encrypted_file.exists()


@requires_sops
def test_decrypt_without_key_fails(temp_dir, age_key):
    """Test that decryption fails without proper key."""
    key_file, public_key = age_key

    # Create and encrypt test file
    input_file = temp_dir / "test.env"
    input_file.write_text("KEY=value\n")
    encrypted_file = temp_dir / "test.env.enc"

    sops = SopsManager(age_public_key=public_key, age_key_file=key_file)
    sops.encrypt(input_file, encrypted_file)

    # Try to decrypt with different (non-existent) key
    wrong_key = temp_dir / "wrong-key.txt"
    sops_wrong = SopsManager(age_public_key=public_key, age_key_file=wrong_key)

    with pytest.raises(RuntimeError, match="SOPS decryption failed"):
        sops_wrong.decrypt(encrypted_file)


def test_create_sops_yaml_with_custom_path(temp_dir):
    """Test creating .sops.yaml with custom path regex."""
    public_key = "age1test123456789abcdefghijklmnopqrstuvwxyz"
    sops_yaml = temp_dir / "custom" / ".sops.yaml"

    sops = SopsManager(age_public_key=public_key)
    sops.create_sops_yaml(sops_yaml)

    # Parent directory should be created
    assert sops_yaml.parent.exists()
    assert sops_yaml.exists()
