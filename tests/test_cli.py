"""Tests for CLI interface."""

from typer.testing import CliRunner

from envseal import __version__
from envseal.cli import app
from envseal.config import Config

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
    assert __version__ in result.stdout


def test_diff_without_config_exits_cleanly(temp_dir, monkeypatch):
    """diff should print a friendly message (not a traceback) when no config exists."""
    missing = temp_dir / "nonexistent" / "config.yaml"
    monkeypatch.setattr(Config, "get_config_path", staticmethod(lambda: missing))

    result = runner.invoke(app, ["diff", "some-repo"])

    assert result.exit_code == 1
    assert "Run 'envseal init'" in result.output


def test_pull_without_config_exits_cleanly(temp_dir, monkeypatch):
    """pull should print a friendly message (not a traceback) when no config exists."""
    missing = temp_dir / "nonexistent" / "config.yaml"
    monkeypatch.setattr(Config, "get_config_path", staticmethod(lambda: missing))

    result = runner.invoke(app, ["pull", "some-repo"])

    assert result.exit_code == 1
    assert "Run 'envseal init'" in result.output
