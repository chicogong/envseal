"""Vault repository management."""

import subprocess
from pathlib import Path

from envseal.config import Config


class VaultManager:
    """Manage vault repository structure and paths."""

    def __init__(self, config: Config):
        self.config = config

    def ensure_vault_structure(self) -> None:
        """Ensure vault directory structure exists."""
        secrets_dir = self.config.vault_path / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)

    def get_vault_path(self, repo_name: str, env_name: str) -> Path:
        """Get the vault path for a specific repo and environment."""
        return self.config.vault_path / "secrets" / repo_name / f"{env_name}.env"

    def map_env_filename(self, filename: str) -> str:
        """Map .env filename to environment name using config mapping."""
        # Check if in mapping
        if filename in self.config.env_mapping:
            return self.config.env_mapping[filename]

        # Otherwise, extract from filename (e.g., .env.custom -> custom)
        if filename.startswith(".env."):
            return filename[5:]  # Remove ".env." prefix

        # Default for .env
        return "local"

    def get_repo_vault_dir(self, repo_name: str) -> Path:
        """Get the vault directory for a specific repo."""
        return self.config.vault_path / "secrets" / repo_name

    def is_git_repo(self) -> bool:
        """Check whether the vault path is inside a Git working tree."""
        result = subprocess.run(
            ["git", "-C", str(self.config.vault_path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def git_commit(self, message: str) -> bool:
        """Stage and commit all changes in the vault.

        Returns True if a commit was created, False if there was nothing to
        commit. Raises RuntimeError if a Git command fails.
        """
        vault = str(self.config.vault_path)

        add = subprocess.run(
            ["git", "-C", vault, "add", "-A"],
            capture_output=True,
            text=True,
        )
        if add.returncode != 0:
            raise RuntimeError(f"git add failed: {add.stderr.strip()}")

        status = subprocess.run(
            ["git", "-C", vault, "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            return False

        commit = subprocess.run(
            ["git", "-C", vault, "commit", "-m", message],
            capture_output=True,
            text=True,
        )
        if commit.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")
        return True

    def git_push(self) -> None:
        """Push the vault repository to its remote.

        Raises RuntimeError if the push fails.
        """
        result = subprocess.run(
            ["git", "-C", str(self.config.vault_path), "push"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git push failed: {result.stderr.strip()}")
