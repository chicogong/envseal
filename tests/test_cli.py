"""Tests for CLI interface."""

from typer.testing import CliRunner

from envseal import __version__
from envseal.broker import SecretBroker
from envseal.catalog import SecretCatalog, SecretMetadata
from envseal.cli import app
from envseal.config import Config
from envseal.keychain import KeychainStore

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


def test_run_prompt_injects_one_command_without_printing_value(monkeypatch):
    """The CLI passes a prompted value to the broker but never renders it."""
    captured = {}

    monkeypatch.setattr("getpass.getpass", lambda prompt: "temporary-test-value")

    def fake_run(self, command, bindings, prompted):
        captured["command"] = command
        captured["bindings"] = bindings
        captured["prompted"] = dict(prompted)
        return 0

    monkeypatch.setattr(SecretBroker, "run", fake_run)
    result = runner.invoke(app, ["run", "--prompt", "TEMP_TOKEN", "--", "demo", "--flag"])

    assert result.exit_code == 0
    assert captured == {
        "command": ["demo", "--flag"],
        "bindings": [],
        "prompted": {"TEMP_TOKEN": "temporary-test-value"},
    }
    assert "temporary-test-value" not in result.output


def test_secret_list_verify_reports_stale_metadata_without_reading_value(monkeypatch):
    item = SecretMetadata(
        reference="demo/prod/API_KEY",
        backend="keychain",
        updated_at="2026-08-24T00:00:00+00:00",
    )
    monkeypatch.setattr(SecretCatalog, "list", lambda self: [item])
    monkeypatch.setattr(KeychainStore, "available", lambda self: True)
    monkeypatch.setattr(KeychainStore, "contains", lambda self, reference: False)

    result = runner.invoke(app, ["secret", "list", "--verify"])

    assert result.exit_code == 0
    assert "demo/prod/API_KEY" in result.output
    assert "missing" in result.output
    assert "stale catalog entry" in result.output
    assert "--catalog-only" in result.output


def test_secret_remove_catalog_only_never_touches_keychain(monkeypatch):
    removed = []
    monkeypatch.setattr(SecretCatalog, "remove", lambda self, reference: removed.append(reference))

    def unexpected_delete(self, reference):
        raise AssertionError("Keychain must not be touched")

    monkeypatch.setattr(KeychainStore, "delete", unexpected_delete)
    result = runner.invoke(
        app,
        ["secret", "remove", "demo/prod/API_KEY", "--catalog-only", "--yes"],
    )

    assert result.exit_code == 0
    assert removed == ["demo/prod/API_KEY"]
    assert "local catalog" in result.output
