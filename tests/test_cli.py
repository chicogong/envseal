"""Tests for CLI interface."""

from typer.testing import CliRunner

from envseal.cli import app

runner = CliRunner()


def test_cli_help():
    """Test CLI help message."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "envseal" in result.stdout.lower()


def test_cli_version():
    """Test CLI version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout
