"""Tests for value-safe local secret brokering."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from envseal.broker import SecretBroker, parse_binding, validate_reference
from envseal.catalog import SecretCatalog
from envseal.guard import HOOK_MARKER, GitGuard, GuardError
from envseal.keychain import KeychainError, KeychainStore


class FakeKeychain:
    def __init__(self, values: dict[str, str]):
        self.values = values

    def get(self, reference: str) -> str:
        return self.values[reference]


def test_parse_binding_accepts_reference():
    assert parse_binding("OPENAI_API_KEY=demo/prod/OPENAI_API_KEY") == (
        "OPENAI_API_KEY",
        "demo/prod/OPENAI_API_KEY",
    )


@pytest.mark.parametrize(
    "binding",
    ["missing", "1BAD=demo/key", "GOOD=", "GOOD=/rooted", "GOOD=demo/../key"],
)
def test_parse_binding_rejects_unsafe_input(binding):
    with pytest.raises(ValueError):
        parse_binding(binding)


@pytest.mark.parametrize("reference", ["-s", "demo//key", "demo/key\nnext"])
def test_reference_rejects_unsafe_input(reference):
    with pytest.raises(ValueError):
        validate_reference(reference)


def test_broker_injects_only_child_environment(monkeypatch):
    captured = {}

    def fake_run(command, env, check):
        captured["command"] = command
        captured["value"] = env["DEMO_TOKEN"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    broker = SecretBroker(FakeKeychain({"demo/dev/TOKEN": "test-only-value"}))

    assert broker.run(["demo", "arg"], ["DEMO_TOKEN=demo/dev/TOKEN"]) == 0
    assert captured == {"command": ["demo", "arg"], "value": "test-only-value"}
    assert "DEMO_TOKEN" not in os.environ


def test_catalog_contains_metadata_only(temp_dir):
    path = temp_dir / "private" / "catalog.json"
    catalog = SecretCatalog(path)
    catalog.record("demo/prod/API_KEY")

    data = json.loads(path.read_text())
    assert data[0]["reference"] == "demo/prod/API_KEY"
    assert set(data[0]) == {"reference", "backend", "updated_at"}
    assert path.stat().st_mode & 0o077 == 0
    assert path.parent.stat().st_mode & 0o077 == 0


def test_catalog_remove(temp_dir):
    catalog = SecretCatalog(temp_dir / "catalog.json")
    catalog.record("demo/dev/A")
    catalog.record("demo/dev/B")
    catalog.remove("demo/dev/A")
    assert [item.reference for item in catalog.list()] == ["demo/dev/B"]


def test_keychain_write_uses_prompt_not_secret_argv(monkeypatch):
    calls = []
    monkeypatch.setattr(KeychainStore, "available", lambda self: True)

    def fake_run(command, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    KeychainStore().put_interactive("demo/prod/API_KEY")

    command = calls[0]
    assert command[-1] == "-w"
    trust_index = command.index("-T")
    assert command[trust_index + 1] == ""
    assert "test-only-value" not in command


def test_keychain_missing_reference_is_value_free(monkeypatch):
    monkeypatch.setattr(KeychainStore, "available", lambda self: True)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 44, stdout="", stderr="sensitive")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(KeychainError, match="demo/prod/API_KEY") as exc:
        KeychainStore().get("demo/prod/API_KEY")
    assert "sensitive" not in str(exc.value)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)


def test_guard_install_refuses_existing_hook(temp_dir):
    repo = temp_dir / "repo"
    _init_repo(repo)
    subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "core.hooksPath", ".git/hooks"],
        check=True,
    )
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho existing\n")

    with pytest.raises(GuardError, match="left unchanged"):
        GitGuard().install(repo)
    assert hook.read_text() == "#!/bin/sh\necho existing\n"


def test_guard_install_creates_managed_hook(temp_dir):
    repo = temp_dir / "repo"
    _init_repo(repo)
    subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "core.hooksPath", ".git/hooks"],
        check=True,
    )
    hook = GitGuard().install(repo)
    assert HOOK_MARKER in hook.read_text()
    assert hook.stat().st_mode & 0o111


def test_guard_supports_linked_worktree(temp_dir):
    main_repo = temp_dir / "main"
    linked = temp_dir / "linked"
    _init_repo(main_repo)
    subprocess.run(["git", "-C", str(main_repo), "config", "user.email", "test@example.com"])
    subprocess.run(["git", "-C", str(main_repo), "config", "user.name", "Test"])
    subprocess.run(
        ["git", "-C", str(main_repo), "config", "--local", "core.hooksPath", ".hooks"],
        check=True,
    )
    (main_repo / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(main_repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(main_repo), "commit", "-m", "initial"], check=True)
    subprocess.run(
        ["git", "-C", str(main_repo), "worktree", "add", "-b", "linked", str(linked)],
        check=True,
        capture_output=True,
    )

    hook = GitGuard().install(linked)
    assert HOOK_MARKER in hook.read_text()


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks is not installed")
def test_guard_blocks_secret_in_initial_commit(temp_dir):
    repo = temp_dir / "repo"
    _init_repo(repo)
    access_key = "AK" + "IA" + "QWERTYUIOPASDFGH"
    (repo / "config.env").write_text(f"AWS_ACCESS_KEY_ID={access_key}\n")
    subprocess.run(["git", "-C", str(repo), "add", "config.env"], check=True)

    assert GitGuard().scan_staged(repo) is False
