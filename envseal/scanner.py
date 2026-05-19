"""Repository and .env file scanning."""

import fnmatch
import hashlib
from dataclasses import dataclass
from pathlib import Path

from envseal.config import ScanConfig


@dataclass
class EnvFile:
    """Represents a found .env file."""

    filepath: Path
    repo_path: Path

    @property
    def filename(self) -> str:
        """Get the filename."""
        return self.filepath.name

    def get_hash(self) -> str:
        """Get SHA256 hash of file contents."""
        return hashlib.sha256(self.filepath.read_bytes()).hexdigest()


class Scanner:
    """Scanner for finding .env files in repositories."""

    def __init__(self, scan_config: ScanConfig):
        self.config = scan_config

    def scan_repo(self, repo_path: Path) -> list[EnvFile]:
        """Scan a repository's top-level directory for .env files.

        Only the repo root is scanned, never subdirectories: a nested .env
        (e.g. sub/dir/.env) would otherwise map to the same vault path as the
        root .env and silently overwrite it. To manage a subdirectory's .env,
        register that subdirectory as its own repo entry.
        """
        env_files: list[EnvFile] = []
        if not repo_path.is_dir():
            return env_files

        for path in sorted(repo_path.iterdir()):
            # Skip if not a file
            if not path.is_file():
                continue

            filename = path.name

            # Never treat backup or template files as env files: `pull --replace`
            # writes a <name>.backup copy; *.example / *.sample are templates with
            # placeholder values, not real secrets.
            if filename.endswith((".backup", ".example", ".sample")):
                continue

            if not any(
                fnmatch.fnmatch(filename, pattern) for pattern in self.config.include_patterns
            ):
                continue

            # Check if matches exclude patterns
            if any(fnmatch.fnmatch(filename, pattern) for pattern in self.config.exclude_patterns):
                continue

            env_files.append(EnvFile(filepath=path, repo_path=repo_path))

        return env_files

    def find_git_repos(self, root_path: Path) -> list[Path]:
        """Find all Git repositories under a root path."""
        repos = []

        for path in root_path.rglob(".git"):
            if path.is_dir():
                repo_path = path.parent
                repos.append(repo_path)

        return repos
