"""Tests for .env file parsing and normalization."""

import pytest

from envseal.dotenvio import DotEnvIO


def test_parse_env_file(temp_dir):
    """Test parsing .env file to dictionary."""
    env_file = temp_dir / ".env"
    env_file.write_text("""
DATABASE_URL=postgres://localhost/db
API_KEY=test123
DEBUG=true
""")

    dotenv = DotEnvIO()
    data = dotenv.parse(env_file)

    assert data["DATABASE_URL"] == "postgres://localhost/db"
    assert data["API_KEY"] == "test123"
    assert data["DEBUG"] == "true"


def test_normalize_sorts_keys(temp_dir):
    """Test normalization sorts keys alphabetically."""
    env_file = temp_dir / ".env"
    env_file.write_text("""
ZEBRA=last
APPLE=first
MIDDLE=middle
""")

    dotenv = DotEnvIO()
    normalized = dotenv.normalize(env_file)

    lines = normalized.strip().split("\n")
    assert lines[0].startswith("APPLE=")
    assert lines[1].startswith("MIDDLE=")
    assert lines[2].startswith("ZEBRA=")


def test_normalize_handles_quotes(temp_dir):
    """Test normalization handles quotes correctly."""
    env_file = temp_dir / ".env"
    env_file.write_text("""
SIMPLE=value
WITH_SPACES="value with spaces"
SPECIAL="value=with=equals"
""")

    dotenv = DotEnvIO()
    normalized = dotenv.normalize(env_file)

    assert 'SIMPLE=value' in normalized
    assert 'WITH_SPACES="value with spaces"' in normalized
    assert 'SPECIAL="value=with=equals"' in normalized


def test_write_normalized(temp_dir):
    """Test writing normalized .env file."""
    output = temp_dir / "output.env"

    data = {
        "ZEBRA": "last",
        "APPLE": "first",
        "WITH_SPACE": "has space",
    }

    dotenv = DotEnvIO()
    dotenv.write(output, data)

    content = output.read_text()
    lines = content.strip().split("\n")

    assert lines[0] == "APPLE=first"
    assert lines[1] == 'WITH_SPACE="has space"'
    assert lines[2] == "ZEBRA=last"


def test_parse_nonexistent_file(temp_dir):
    """Test parsing nonexistent file raises FileNotFoundError."""
    nonexistent = temp_dir / "nonexistent.env"
    dotenv = DotEnvIO()

    with pytest.raises(FileNotFoundError) as exc_info:
        dotenv.parse(nonexistent)

    assert "Environment file not found" in str(exc_info.value)
    assert str(nonexistent) in str(exc_info.value)


def test_write_to_readonly_directory(temp_dir):
    """Test writing to read-only directory raises OSError."""
    import os
    import stat

    # Create a directory and make it read-only
    readonly_dir = temp_dir / "readonly"
    readonly_dir.mkdir()
    os.chmod(readonly_dir, stat.S_IRUSR | stat.S_IXUSR)

    output = readonly_dir / "test.env"
    dotenv = DotEnvIO()

    try:
        with pytest.raises(OSError) as exc_info:
            dotenv.write(output, {"KEY": "value"})

        assert "Failed to write" in str(exc_info.value)
    finally:
        # Restore permissions for cleanup
        os.chmod(readonly_dir, stat.S_IRWXU)


def test_handle_none_values(temp_dir):
    """Test handling None values from dotenv_values."""
    output = temp_dir / "output.env"

    # Simulate None values that can come from dotenv_values
    data = {
        "KEY1": "value1",
        "KEY2": None,  # None value
        "KEY3": "value3",
    }

    dotenv = DotEnvIO()
    dotenv.write(output, data)

    content = output.read_text()
    content.strip().split("\n")

    assert "KEY1=value1" in content
    assert "KEY2=" in content  # Should be empty string
    assert "KEY3=value3" in content


def test_escape_quotes_in_values(temp_dir):
    """Test escaping existing quotes in values."""
    output = temp_dir / "output.env"

    data = {
        "QUOTED": 'value with "quotes" inside',
        "SIMPLE": "noquotes",
    }

    dotenv = DotEnvIO()
    dotenv.write(output, data)

    content = output.read_text()

    # Should escape the quotes
    assert 'QUOTED="value with \\"quotes\\" inside"' in content
    assert "SIMPLE=noquotes" in content


def test_empty_value_handling(temp_dir):
    """Test handling empty string values."""
    output = temp_dir / "output.env"

    data = {
        "EMPTY": "",
        "NOT_EMPTY": "value",
    }

    dotenv = DotEnvIO()
    dotenv.write(output, data)

    content = output.read_text()
    content.strip().split("\n")

    assert "EMPTY=" in content
    assert "NOT_EMPTY=value" in content
