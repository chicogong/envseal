"""Change detection and collection for envseal update command."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from envseal.config import Config
from envseal.diffing import DiffCalculator, DiffResult
from envseal.dotenvio import DotEnvIO
from envseal.scanner import EnvFile, Scanner
from envseal.sops import SopsManager
from envseal.vault import VaultManager


@dataclass
class ChangeInfo:
    """Information about a changed .env file."""
    repo_name: str
    env_name: str
    env_file: EnvFile
    diff: DiffResult
    vault_path: Path

    @property
    def change_summary(self) -> str:
        """Get human-readable change summary."""
        parts = []
        if self.diff.added:
            parts.append(f"{len(self.diff.added)} added")
        if self.diff.modified:
            parts.append(f"{len(self.diff.modified)} modified")
        if self.diff.removed:
            parts.append(f"{len(self.diff.removed)} removed")

        if not parts:
            return "no changes"

        total = len(self.diff.added) + len(self.diff.modified) + len(self.diff.removed)
        key_word = "key" if total == 1 else "keys"
        return f"{total} {key_word} changed ({', '.join(parts)})"


class ChangeCollector:
    """Collect changes across all repositories."""

    def __init__(
        self,
        config: Config,
        scanner: Scanner,
        vault_manager: VaultManager,
        sops: SopsManager,
        dotenv_io: DotEnvIO,
        diff_calc: DiffCalculator,
    ):
        self.config = config
        self.scanner = scanner
        self.vault_manager = vault_manager
        self.sops = sops
        self.dotenv_io = dotenv_io
        self.diff_calc = diff_calc

    def collect_changes(self, env_filter: Optional[str] = None) -> list[ChangeInfo]:
        """Collect all changes across repositories.

        Args:
            env_filter: If specified, only collect changes for this environment

        Returns:
            List of ChangeInfo objects for files with changes
        """
        changes = []

        for repo in self.config.repos:
            repo_changes = self._scan_repo_changes(repo.name, env_filter)
            changes.extend(repo_changes)

        return changes

    def _scan_repo_changes(self, repo_name: str, env_filter: Optional[str] = None) -> list[ChangeInfo]:
        """Scan a repository for changes.

        Args:
            repo_name: Name of the repository
            env_filter: Optional environment filter

        Returns:
            List of ChangeInfo objects for this repository
        """
        changes = []

        # Find the repository object
        repo = next((r for r in self.config.repos if r.name == repo_name), None)
        if not repo:
            return changes

        # Find all .env files in the repository
        env_files = self.scanner.scan_repo(repo.path)
        if not env_files:
            return changes

        for env_file in env_files:
            # Get environment name from filename
            env_name = self.vault_manager.map_env_filename(env_file.filename)

            # Apply environment filter if specified
            if env_filter and env_name != env_filter:
                continue

            change_info = self._check_file_changes(repo_name, env_file, env_name)
            if change_info:
                changes.append(change_info)

        return changes

    def _check_file_changes(self, repo_name: str, env_file: EnvFile, env_name: str) -> Optional[ChangeInfo]:
        """Check if a file has changes compared to vault.

        Args:
            repo_name: Name of the repository
            env_file: EnvFile object
            env_name: Environment name

        Returns:
            ChangeInfo if changes detected, None otherwise
        """
        # Get vault path for this file
        vault_path = self.vault_manager.get_vault_path(repo_name, env_name)

        # Skip if file doesn't exist in vault (needs push, not update)
        if not vault_path.exists():
            return None

        try:
            # Normalize local file
            local_normalized = self.dotenv_io.normalize(env_file.filepath)

            # Decrypt vault file
            vault_decrypted = self.sops.decrypt(vault_path)

            # Calculate differences (vault first, then local - same as status command)
            diff = self.diff_calc.calculate(vault_decrypted, local_normalized)

            # If changes found, create ChangeInfo
            if diff.added or diff.modified or diff.removed:
                return ChangeInfo(
                    repo_name=repo_name,
                    env_name=env_name,
                    env_file=env_file,
                    diff=diff,
                    vault_path=vault_path,
                )

        except Exception:
            # Skip files that can't be decrypted or compared
            pass

        return None