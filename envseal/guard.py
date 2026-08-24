"""Git secret-leak guard powered by Gitleaks with full redaction."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

HOOK_MARKER = "# envseal-managed-secret-guard"


class GuardError(RuntimeError):
    """A safe guard operation failure."""


class GitGuard:
    """Scan staged Git changes and optionally install a pre-commit hook."""

    def available(self) -> bool:
        return shutil.which("gitleaks") is not None

    def scan_staged(self, repo: Path) -> bool:
        """Return True when staged changes contain no detected secrets."""
        self._require_repo(repo)
        if not self.available():
            raise GuardError("Gitleaks is required; install it with: brew install gitleaks")

        # ``gitleaks git --staged`` currently scans zero bytes on an unborn
        # branch.  Feed the staged diff over a pipe for the first commit so the
        # most important commit is not accidentally left unprotected.
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if head.returncode != 0:
            return self._scan_initial_staged(repo)

        result = subprocess.run(
            [
                "gitleaks",
                "git",
                "--staged",
                "--redact=100",
                "--no-banner",
                "--no-color",
                str(repo),
            ],
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise GuardError(f"Gitleaks failed with exit code {result.returncode}")
        return result.returncode == 0

    @staticmethod
    def _scan_initial_staged(repo: Path) -> bool:
        diff = subprocess.Popen(
            [
                "git",
                "-C",
                str(repo),
                "diff",
                "--cached",
                "--no-color",
                "--no-ext-diff",
            ],
            stdout=subprocess.PIPE,
        )
        assert diff.stdout is not None
        result = subprocess.run(
            ["gitleaks", "stdin", "--redact=100", "--no-banner", "--no-color"],
            stdin=diff.stdout,
            check=False,
        )
        diff.stdout.close()
        diff_code = diff.wait()
        if diff_code != 0:
            raise GuardError(f"Git staged diff failed with exit code {diff_code}")
        if result.returncode not in {0, 1}:
            raise GuardError(f"Gitleaks failed with exit code {result.returncode}")
        return result.returncode == 0

    def install(self, repo: Path) -> Path:
        """Install a value-safe pre-commit hook, refusing to overwrite others."""
        self._require_repo(repo)
        hook_scope = subprocess.run(
            ["git", "-C", str(repo), "config", "--show-scope", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
            check=False,
        )
        if hook_scope.returncode == 0:
            scope = hook_scope.stdout.split(maxsplit=1)[0]
            if scope not in {"local", "worktree"}:
                raise GuardError(
                    "A shared Git hooksPath is configured; left it unchanged. "
                    "Add 'envseal guard staged --repo .' to that hook manager instead."
                )
        hook_result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-path", "hooks/pre-commit"],
            capture_output=True,
            text=True,
            check=False,
        )
        if hook_result.returncode != 0:
            raise GuardError(f"Cannot resolve Git hooks directory: {repo}")
        hook = Path(hook_result.stdout.strip())
        if not hook.is_absolute():
            hook = (repo / hook).resolve()
        common_result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        common_dir = Path(common_result.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = (repo / common_dir).resolve()
        allowed_roots = (repo.resolve(), common_dir)
        if not any(_is_within(hook, root) for root in allowed_roots):
            raise GuardError(f"Hooks path is outside this repository; left unchanged: {hook}")
        if hook.exists() and HOOK_MARKER not in hook.read_text(errors="replace"):
            raise GuardError(f"Existing pre-commit hook left unchanged: {hook}")
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(
            "#!/bin/sh\n"
            f"{HOOK_MARKER}\n"
            "repo=$(git rev-parse --show-toplevel) || exit 2\n"
            'exec envseal guard staged --repo "$repo"\n'
        )
        os.chmod(hook, 0o755)
        return hook

    @staticmethod
    def _require_repo(repo: Path) -> None:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise GuardError(f"Not a Git working tree: {repo}")


def _is_within(path: Path, root: Path) -> bool:
    """Python 3.9-compatible containment check for resolved filesystem paths."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
