"""Tests for .env file parsing and normalization."""

from pathlib import Path
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
